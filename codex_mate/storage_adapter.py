from __future__ import annotations

import base64
import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from codex_mate import codex_storage
from codex_mate.backup_store import BackupStore
from codex_mate.models import DeleteResult, DeleteStatus, SessionRef


class SQLiteStorageAdapter:
    def __init__(self, db_path: Path, backup_store: BackupStore):
        self.db_path = db_path
        self.codex_home = codex_storage.codex_home_for_db_path(db_path) or db_path.parent
        self.backup_store = backup_store

    def supports_schema(self) -> bool:
        with sqlite3.connect(self.db_path) as db:
            return self._schema_kind(db) is not None

    def delete_local(self, session: SessionRef) -> DeleteResult:
        if not self.db_path.exists():
            return DeleteResult(DeleteStatus.FAILED, session.session_id, f"Database not found: {self.db_path}")

        with sqlite3.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            schema_kind = self._schema_kind(db)
            if schema_kind is None:
                return DeleteResult(DeleteStatus.FAILED, session.session_id, "Unsupported local storage schema")
            if schema_kind == "codex_threads":
                return self._delete_codex_thread(db, session)
            if schema_kind == "codex_automation_runs":
                return self._delete_codex_automation_run(db, session)
            return self._delete_generic_session(db, session)

    def undo(self, token: str) -> DeleteResult:
        backup = self.backup_store.read_backup(token)
        session_id = backup["session_id"]
        with sqlite3.connect(self.db_path) as db:
            for table, rows in backup["tables"].items():
                if table.startswith("__"):
                    continue
                for row in rows:
                    self._insert_row(db, table, row)
            db.commit()
        for file_backup in backup["tables"].get("__files", []):
            path = Path(file_backup["path"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(base64.b64decode(file_backup["content_b64"]))
        return DeleteResult(DeleteStatus.UNDONE, session_id, "Local session restored from backup", undo_token=token)

    def find_archived_thread_by_title(self, title: str) -> SessionRef | None:
        if not self.db_path.exists():
            return None
        with sqlite3.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            if self._schema_kind(db) != "codex_threads" or not self._has_columns(db, "threads", {"archived"}):
                return None
            row = db.execute(
                """
                SELECT id, title FROM threads
                WHERE archived = 1 AND (title = ? OR title LIKE ? OR ? LIKE '%' || title || '%')
                ORDER BY archived_at DESC LIMIT 1
                """,
                (title, f"%{title}%", title),
            ).fetchone()
            return SessionRef(session_id=str(row["id"]), title=str(row["title"] or title)) if row else None

    def move_codex_thread_workspace(self, session: SessionRef, target_cwd: str) -> dict[str, object]:
        target = target_cwd.strip()
        if not target:
            return {"status": "failed", "session_id": session.session_id, "message": "目标项目路径为空"}
        return self._move_codex_thread_cwd(session, target)

    def move_codex_thread_projectless(self, session: SessionRef) -> dict[str, object]:
        return self._move_codex_thread_cwd(session, "")

    def codex_thread_sort_key(self, session: SessionRef) -> dict[str, object]:
        if not self.db_path.exists():
            return {"status": "failed", "session_id": session.session_id, "message": f"Database not found: {self.db_path}"}
        try:
            with sqlite3.connect(self.db_path) as db:
                db.row_factory = sqlite3.Row
                if self._schema_kind(db) != "codex_threads":
                    return {"status": "failed", "session_id": session.session_id, "message": "Unsupported local storage schema"}
                thread_id = self._normalize_codex_thread_id(session.session_id)
                payload = self._fetch_thread_timestamp_payload(db, thread_id)
                if payload is None:
                    return {"status": "failed", "session_id": thread_id, "message": "Thread not found in local storage"}
                return {"status": "ok", "session_id": thread_id, **payload}
        except sqlite3.Error as exc:
            return {"status": "failed", "session_id": session.session_id, "message": str(exc)}

    def codex_thread_sort_keys(self, sessions: list[SessionRef]) -> dict[str, object]:
        if not self.db_path.exists():
            return {"status": "failed", "message": f"Database not found: {self.db_path}", "sort_keys": []}
        thread_ids: list[str] = []
        for session in sessions:
            if not session.session_id:
                continue
            thread_id = self._normalize_codex_thread_id(session.session_id)
            if thread_id not in thread_ids:
                thread_ids.append(thread_id)
            if len(thread_ids) >= 200:
                break
        if not thread_ids:
            return {"status": "ok", "sort_keys": []}
        try:
            with sqlite3.connect(self.db_path) as db:
                db.row_factory = sqlite3.Row
                if self._schema_kind(db) != "codex_threads":
                    return {"status": "failed", "message": "Unsupported local storage schema", "sort_keys": []}
                sort_keys = []
                for thread_id in thread_ids:
                    payload = self._fetch_thread_timestamp_payload(db, thread_id)
                    if payload is not None:
                        sort_keys.append({"session_id": thread_id, **payload})
                return {"status": "ok", "sort_keys": sort_keys}
        except sqlite3.Error as exc:
            return {"status": "failed", "message": str(exc), "sort_keys": []}

    def _delete_generic_session(self, db: sqlite3.Connection, session: SessionRef) -> DeleteResult:
        session_rows = self._select_dicts(db, "SELECT * FROM sessions WHERE id = ?", (session.session_id,))
        if not session_rows:
            return DeleteResult(DeleteStatus.FAILED, session.session_id, "Session not found in local storage")
        message_rows = self._select_dicts(db, "SELECT * FROM messages WHERE session_id = ?", (session.session_id,)) if self._has_table(db, "messages") else []
        token = self.backup_store.write_backup(
            session_id=session.session_id,
            source_db=str(self.db_path),
            tables={"sessions": session_rows, "messages": message_rows},
        )
        if self._has_table(db, "messages"):
            db.execute("DELETE FROM messages WHERE session_id = ?", (session.session_id,))
        db.execute("DELETE FROM sessions WHERE id = ?", (session.session_id,))
        db.commit()
        return self._local_deleted(session.session_id, token)

    def _delete_codex_thread(self, db: sqlite3.Connection, session: SessionRef) -> DeleteResult:
        thread_id = self._normalize_codex_thread_id(session.session_id)
        thread_rows = self._select_dicts(db, "SELECT * FROM threads WHERE id = ?", (thread_id,))
        if not thread_rows:
            return self._delete_codex_ghost_thread(thread_id, session.session_id)
        cwd = str(thread_rows[0].get("cwd") or "") if "cwd" in thread_rows[0] else ""

        tables: dict[str, list[dict[str, Any]]] = {"threads": thread_rows}
        self._backup_related_rows(db, tables, "thread_dynamic_tools", "thread_id = ?", (thread_id,))
        self._backup_related_rows(db, tables, "thread_goals", "thread_id = ?", (thread_id,))
        self._backup_related_rows(db, tables, "thread_spawn_edges", "parent_thread_id = ? OR child_thread_id = ?", (thread_id, thread_id))
        self._backup_related_rows(db, tables, "stage1_outputs", "thread_id = ?", (thread_id,))
        self._backup_related_rows(db, tables, "agent_job_items", "assigned_thread_id = ?", (thread_id,))

        file_backups = self._rollout_file_backups(thread_rows, thread_id)
        sidecar_backups = self._codex_sidecar_file_backups()
        if file_backups:
            tables["__files"] = list(file_backups)
        if sidecar_backups:
            tables.setdefault("__files", []).extend(sidecar_backups)

        token = self.backup_store.write_backup(thread_id, str(self.db_path), tables)

        self._delete_related_rows(db, "thread_dynamic_tools", "thread_id = ?", (thread_id,))
        self._delete_related_rows(db, "thread_goals", "thread_id = ?", (thread_id,))
        self._delete_related_rows(db, "thread_spawn_edges", "parent_thread_id = ? OR child_thread_id = ?", (thread_id, thread_id))
        self._delete_related_rows(db, "stage1_outputs", "thread_id = ?", (thread_id,))
        if self._has_table(db, "agent_job_items") and self._has_columns(db, "agent_job_items", {"assigned_thread_id"}):
            db.execute("UPDATE agent_job_items SET assigned_thread_id = NULL WHERE assigned_thread_id = ?", (thread_id,))
        db.execute("DELETE FROM threads WHERE id = ?", (thread_id,))
        db.commit()

        file_delete_errors = []
        for file_backup in file_backups:
            path = Path(file_backup["path"])
            try:
                path.unlink(missing_ok=True)
            except OSError as exc:
                file_delete_errors.append(f"{path}: {exc}")

        sidecar_errors = self._remove_codex_thread_sidecar_refs(thread_id, cwd)
        cleanup_errors = file_delete_errors + sidecar_errors
        if cleanup_errors:
            if file_delete_errors and not sidecar_errors:
                message = "本地数据库已删除，但文件删除失败：" + "; ".join(cleanup_errors)
            else:
                message = "本地数据库已删除，但清理索引/文件失败：" + "; ".join(cleanup_errors)
            return DeleteResult(DeleteStatus.FAILED, thread_id, message, undo_token=token, backup_path=str(self.backup_store.path_for(token)))

        return self._local_deleted(thread_id, token)

    def _delete_codex_automation_run(self, db: sqlite3.Connection, session: SessionRef) -> DeleteResult:
        thread_id = self._normalize_codex_thread_id(session.session_id)
        rows = self._select_dicts(db, "SELECT * FROM automation_runs WHERE thread_id = ?", (thread_id,))
        if not rows:
            return DeleteResult(DeleteStatus.FAILED, session.session_id, "Thread not found in local storage")
        token = self.backup_store.write_backup(
            session_id=thread_id,
            source_db=str(self.db_path),
            tables={"automation_runs": rows},
        )
        db.execute("DELETE FROM automation_runs WHERE thread_id = ?", (thread_id,))
        db.commit()
        return self._local_deleted(thread_id, token)

    def _delete_codex_ghost_thread(self, thread_id: str, original_session_id: str) -> DeleteResult:
        file_backups = self._rollout_file_backups([], thread_id)
        sidecar_has_refs = self._codex_sidecar_refs_exist(thread_id)
        if not file_backups and not sidecar_has_refs:
            return DeleteResult(DeleteStatus.FAILED, original_session_id, "Thread not found in local storage")

        tables: dict[str, list[dict[str, Any]]] = {}
        if file_backups:
            tables["__files"] = list(file_backups)
        if sidecar_has_refs:
            tables.setdefault("__files", []).extend(self._codex_sidecar_file_backups())
        token = self.backup_store.write_backup(thread_id, str(self.db_path), tables)

        file_delete_errors = []
        for file_backup in file_backups:
            path = Path(file_backup["path"])
            try:
                path.unlink(missing_ok=True)
            except OSError as exc:
                file_delete_errors.append(f"{path}: {exc}")
        sidecar_errors = self._remove_codex_thread_sidecar_refs(thread_id, "")
        cleanup_errors = file_delete_errors + sidecar_errors
        if cleanup_errors:
            return DeleteResult(DeleteStatus.FAILED, thread_id, "本地数据库无此会话，但清理残留索引/文件失败：" + "; ".join(cleanup_errors), undo_token=token, backup_path=str(self.backup_store.path_for(token)))
        return self._local_deleted(thread_id, token)

    def _move_codex_thread_cwd(self, session: SessionRef, target_cwd: str) -> dict[str, object]:
        if not self.db_path.exists():
            return {"status": "failed", "session_id": session.session_id, "message": f"Database not found: {self.db_path}"}
        try:
            with sqlite3.connect(self.db_path) as db:
                db.row_factory = sqlite3.Row
                if self._schema_kind(db) != "codex_threads" or not self._has_columns(db, "threads", {"cwd", "rollout_path"}):
                    return {"status": "failed", "session_id": session.session_id, "message": "Unsupported local storage schema"}
                thread_id = self._normalize_codex_thread_id(session.session_id)
                columns = ["id", "title", "cwd", "rollout_path", *self._codex_thread_timestamp_columns(db)]
                selected = ", ".join(f'"{column}"' for column in columns)
                row = db.execute(f"SELECT {selected} FROM threads WHERE id = ?", (thread_id,)).fetchone()
                if row is None:
                    return {"status": "failed", "session_id": thread_id, "message": "Thread not found in local storage"}
                thread = dict(row)
                previous_cwd = str(thread.get("cwd") or "")
                db.execute("UPDATE threads SET cwd = ? WHERE id = ?", (target_cwd, thread_id))
                db.commit()
        except sqlite3.Error as exc:
            return {"status": "failed", "session_id": session.session_id, "message": str(exc)}

        rollout_updated, rollout_error = self._update_rollout_session_meta_cwd(str(thread.get("rollout_path") or ""), thread_id, target_cwd)
        global_state_error = self._move_thread_in_global_state(thread_id, target_cwd)
        payload: dict[str, object] = {
            "status": "moved",
            "session_id": thread_id,
            "message": "已移动对话",
            "previous_cwd": previous_cwd,
            "target_cwd": target_cwd,
            "rollout_updated": rollout_updated,
            "rollout_error": rollout_error,
        }
        if global_state_error:
            payload["global_state_error"] = global_state_error
        payload.update(self._timestamp_payload_from_row(thread))
        return payload

    def _normalize_codex_thread_id(self, session_id: str) -> str:
        return session_id.removeprefix("local:")

    def _codex_thread_id_variants(self, thread_id: str) -> set[str]:
        bare = self._normalize_codex_thread_id(thread_id)
        return {bare, f"local:{bare}"}

    def _schema_kind(self, db: sqlite3.Connection) -> str | None:
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        if "sessions" in tables:
            session_cols = {row[1] for row in db.execute("PRAGMA table_info(sessions)")}
            if {"id", "title"}.issubset(session_cols):
                if "messages" in tables:
                    message_cols = {row[1] for row in db.execute("PRAGMA table_info(messages)")}
                    return "generic_sessions" if "session_id" in message_cols else None
                return "generic_sessions"
        if "threads" in tables:
            thread_cols = {row[1] for row in db.execute("PRAGMA table_info(threads)")}
            if {"id", "title", "rollout_path"}.issubset(thread_cols):
                return "codex_threads"
        if "automation_runs" in tables:
            run_cols = {row[1] for row in db.execute("PRAGMA table_info(automation_runs)")}
            if "thread_id" in run_cols:
                return "codex_automation_runs"
        return None

    def _backup_related_rows(self, db: sqlite3.Connection, tables: dict[str, list[dict[str, Any]]], table: str, where: str, params: tuple[Any, ...]) -> None:
        if self._has_table(db, table):
            tables[table] = self._select_dicts(db, f'SELECT * FROM "{table}" WHERE {where}', params)

    def _delete_related_rows(self, db: sqlite3.Connection, table: str, where: str, params: tuple[Any, ...]) -> None:
        if self._has_table(db, table):
            db.execute(f'DELETE FROM "{table}" WHERE {where}', params)

    def _rollout_file_backups(self, thread_rows: list[dict[str, Any]], thread_id: str | None = None) -> list[dict[str, Any]]:
        file_backups = []
        seen: set[Path] = set()
        for row in thread_rows:
            rollout_path = row.get("rollout_path")
            if not rollout_path:
                continue
            path = Path(str(rollout_path))
            if path.is_file() and path not in seen:
                file_backups.append({"path": str(path), "content_b64": base64.b64encode(path.read_bytes()).decode("ascii")})
                seen.add(path)
        if thread_id:
            for path in self._session_files_for_thread(thread_id):
                if path not in seen:
                    file_backups.append({"path": str(path), "content_b64": base64.b64encode(path.read_bytes()).decode("ascii")})
                    seen.add(path)
        return file_backups

    def _session_files_for_thread(self, thread_id: str) -> list[Path]:
        variants = self._codex_thread_id_variants(thread_id)
        matches = []
        for sessions_dir in codex_storage.rollout_dirs(self.codex_home):
            for path in sorted(sessions_dir.rglob("rollout-*.jsonl")):
                try:
                    with path.open("r", encoding="utf-8") as file:
                        first_line = file.readline()
                except OSError:
                    continue
                if not first_line.strip():
                    continue
                try:
                    item = json.loads(first_line)
                except json.JSONDecodeError:
                    continue
                payload = item.get("payload")
                if item.get("type") == "session_meta" and isinstance(payload, dict) and str(payload.get("id") or "") in variants:
                    matches.append(path)
        return matches

    def _codex_sidecar_file_backups(self) -> list[dict[str, str]]:
        backups = []
        for path in (self.codex_home / "session_index.jsonl", self.codex_home / ".codex-global-state.json"):
            if path.is_file():
                backups.append({"path": str(path), "content_b64": base64.b64encode(path.read_bytes()).decode("ascii")})
        return backups

    def _codex_thread_timestamp_columns(self, db: sqlite3.Connection) -> list[str]:
        existing = {row[1] for row in db.execute('PRAGMA table_info("threads")')}
        return [column for column in ("updated_at", "updated_at_ms", "created_at_ms") if column in existing]

    def _timestamp_payload_from_row(self, row: dict[str, Any]) -> dict[str, object]:
        return {column: row.get(column) for column in ("updated_at", "updated_at_ms", "created_at_ms")}

    def _fetch_thread_timestamp_payload(self, db: sqlite3.Connection, thread_id: str) -> dict[str, object] | None:
        columns = ["id", *self._codex_thread_timestamp_columns(db)]
        selected = ", ".join(f'"{column}"' for column in columns)
        row = db.execute(f"SELECT {selected} FROM threads WHERE id = ?", (thread_id,)).fetchone()
        if row is None:
            return None
        return self._timestamp_payload_from_row(dict(row))

    def _update_rollout_session_meta_cwd(self, rollout_path: str, thread_id: str, target_cwd: str) -> tuple[bool, str]:
        paths: list[Path] = []
        if rollout_path:
            path = Path(rollout_path)
            if path.is_file():
                paths.append(path)
        for path in self._session_files_for_thread(thread_id):
            if path not in paths:
                paths.append(path)
        changed = False
        errors = []
        for path in paths:
            try:
                changed = self._update_rollout_file_session_meta_cwd(path, thread_id, target_cwd) or changed
            except (OSError, json.JSONDecodeError) as exc:
                errors.append(f"{path}: {exc}")
        return changed, "; ".join(errors)

    def _update_rollout_file_session_meta_cwd(self, path: Path, thread_id: str, target_cwd: str) -> bool:
        variants = self._codex_thread_id_variants(thread_id)
        output = []
        changed = False
        for line in path.read_text(encoding="utf-8").splitlines(keepends=True):
            body = line[:-1] if line.endswith("\n") else line
            end = "\n" if line.endswith("\n") else ""
            raw = line
            if body.strip():
                try:
                    item = json.loads(body)
                except json.JSONDecodeError:
                    output.append(raw)
                    continue
                payload = item.get("payload") if isinstance(item, dict) else None
                if item.get("type") == "session_meta" and isinstance(payload, dict) and str(payload.get("id") or "") in variants and payload.get("cwd") != target_cwd:
                    payload["cwd"] = target_cwd
                    raw = json.dumps(item, ensure_ascii=False, separators=(",", ":")) + end
                    changed = True
            output.append(raw)
        if changed:
            self._atomic_write_text(path, "".join(output))
        return changed

    def _move_thread_in_global_state(self, thread_id: str, target_cwd: str) -> str:
        path = self.codex_home / ".codex-global-state.json"
        state: dict[str, Any] = {}
        if path.exists():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                return str(exc)
            if isinstance(loaded, dict):
                state = loaded
        variants = self._codex_thread_id_variants(thread_id)
        bare_id = self._normalize_codex_thread_id(thread_id)
        projectless_ids = state.get("projectless-thread-ids")
        if not isinstance(projectless_ids, list):
            projectless_ids = []
        next_projectless = [item for item in projectless_ids if not (isinstance(item, str) and item in variants)]
        hints = state.get("thread-workspace-root-hints")
        if not isinstance(hints, dict):
            hints = {}
        next_hints = {key: value for key, value in hints.items() if not (isinstance(key, str) and key in variants)}
        if target_cwd:
            next_hints[bare_id] = target_cwd
        elif bare_id not in next_projectless:
            next_projectless.append(bare_id)
        state["projectless-thread-ids"] = next_projectless
        state["thread-workspace-root-hints"] = next_hints
        try:
            self._atomic_write_text(path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")
        except OSError as exc:
            return str(exc)
        return ""

    def _remove_codex_thread_sidecar_refs(self, thread_id: str, cwd: str = "") -> list[str]:
        errors = []
        cleanup_calls = (
            lambda: self._remove_thread_from_session_index(thread_id),
            lambda: self._remove_thread_from_global_state(thread_id, cwd),
        )
        for cleanup in cleanup_calls:
            try:
                cleanup()
            except OSError as exc:
                errors.append(str(exc))
        return errors

    def _codex_sidecar_refs_exist(self, thread_id: str) -> bool:
        variants = self._codex_thread_id_variants(thread_id)
        index_path = self.codex_home / "session_index.jsonl"
        if index_path.exists():
            for line in index_path.read_text(encoding="utf-8").splitlines():
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(item, dict) and str(item.get("id") or "") in variants:
                    return True
        global_state_path = self.codex_home / ".codex-global-state.json"
        if global_state_path.exists():
            try:
                state = json.loads(global_state_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return False
            return self._contains_thread_keys_or_list_values(state, variants)
        return False

    def _remove_thread_from_session_index(self, thread_id: str) -> None:
        path = self.codex_home / "session_index.jsonl"
        if not path.exists():
            return
        variants = self._codex_thread_id_variants(thread_id)
        changed = False
        kept_lines = []
        for line in path.read_text(encoding="utf-8").splitlines(keepends=True):
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                kept_lines.append(line)
                continue
            if isinstance(item, dict) and str(item.get("id") or "") in variants:
                changed = True
                continue
            kept_lines.append(line)
        if changed:
            self._atomic_write_text(path, "".join(kept_lines))

    def _remove_thread_from_global_state(self, thread_id: str, cwd: str = "") -> None:
        path = self.codex_home / ".codex-global-state.json"
        if not path.exists():
            return
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return
        if not isinstance(state, dict):
            return
        variants = self._codex_thread_id_variants(thread_id)
        cleaned, changed = self._remove_thread_keys_and_list_values(state, variants)
        if cwd and not self._workspace_root_still_used(cwd):
            cleaned, workspace_changed = self._remove_workspace_root_values(cleaned, cwd)
            changed = changed or workspace_changed
        if changed:
            self._atomic_write_text(path, json.dumps(cleaned, ensure_ascii=False, indent=2) + "\n")

    def _workspace_root_still_used(self, cwd: str) -> bool:
        if not cwd or not self._has_table_in_pathless_connection("threads"):
            return False
        try:
            with sqlite3.connect(self.db_path) as db:
                db.row_factory = sqlite3.Row
                if not self._has_table(db, "threads") or not self._has_columns(db, "threads", {"cwd"}):
                    return False
                where = "cwd = ?"
                if self._has_columns(db, "threads", {"archived"}):
                    where += " AND archived = 0"
                return db.execute(f"SELECT 1 FROM threads WHERE {where} LIMIT 1", (cwd,)).fetchone() is not None
        except sqlite3.Error:
            return False

    def _has_table_in_pathless_connection(self, table: str) -> bool:
        if not self.db_path.exists():
            return False
        try:
            with sqlite3.connect(self.db_path) as db:
                return self._has_table(db, table)
        except sqlite3.Error:
            return False

    def _remove_workspace_root_values(self, value: Any, cwd: str) -> tuple[Any, bool]:
        if isinstance(value, dict):
            changed = False
            cleaned: dict[str, Any] = {}
            for key, item in value.items():
                if key in {"project-order", "electron-saved-workspace-roots"} and isinstance(item, list):
                    next_item = [entry for entry in item if not (isinstance(entry, str) and entry == cwd)]
                    cleaned[key] = next_item
                    changed = changed or len(next_item) != len(item)
                    continue
                next_item, item_changed = self._remove_workspace_root_values(item, cwd)
                cleaned[key] = next_item
                changed = changed or item_changed
            return cleaned, changed
        if isinstance(value, list):
            changed = False
            cleaned_list = []
            for item in value:
                next_item, item_changed = self._remove_workspace_root_values(item, cwd)
                cleaned_list.append(next_item)
                changed = changed or item_changed
            return cleaned_list, changed
        return value, False

    def _remove_thread_keys_and_list_values(self, value: Any, variants: set[str]) -> tuple[Any, bool]:
        if isinstance(value, dict):
            changed = False
            cleaned: dict[str, Any] = {}
            for key, item in value.items():
                if isinstance(key, str) and key in variants:
                    changed = True
                    continue
                next_item, item_changed = self._remove_thread_keys_and_list_values(item, variants)
                cleaned[key] = next_item
                changed = changed or item_changed
            return cleaned, changed
        if isinstance(value, list):
            changed = False
            cleaned_list = []
            for item in value:
                if isinstance(item, str) and item in variants:
                    changed = True
                    continue
                if isinstance(item, dict) and self._object_identifies_thread(item, variants):
                    changed = True
                    continue
                next_item, item_changed = self._remove_thread_keys_and_list_values(item, variants)
                cleaned_list.append(next_item)
                changed = changed or item_changed
            return cleaned_list, changed
        return value, False

    def _object_identifies_thread(self, value: dict[str, Any], variants: set[str]) -> bool:
        for key in ("id", "thread_id", "threadId", "session_id", "sessionId", "conversation_id", "conversationId"):
            if isinstance(value.get(key), str) and value[key] in variants:
                return True
        return False

    def _contains_thread_keys_or_list_values(self, value: Any, variants: set[str]) -> bool:
        if isinstance(value, dict):
            if self._object_identifies_thread(value, variants):
                return True
            for key, item in value.items():
                if isinstance(key, str) and key in variants:
                    return True
                if self._contains_thread_keys_or_list_values(item, variants):
                    return True
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item in variants:
                    return True
                if self._contains_thread_keys_or_list_values(item, variants):
                    return True
        return False

    def _atomic_write_text(self, path: Path, text: str) -> None:
        temp = path.with_name(f".{path.name}.codex-mate-{time.time_ns()}.tmp")
        try:
            temp.write_text(text, encoding="utf-8", newline="")
            temp.replace(path)
        finally:
            if temp.exists():
                temp.unlink()

    def _local_deleted(self, session_id: str, token: str) -> DeleteResult:
        return DeleteResult(
            DeleteStatus.LOCAL_DELETED,
            session_id,
            "已从本地存储删除",
            undo_token=token,
            backup_path=str(self.backup_store.path_for(token)),
        )

    def _has_table(self, db: sqlite3.Connection, table: str) -> bool:
        return db.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone() is not None

    def _has_columns(self, db: sqlite3.Connection, table: str, columns: set[str]) -> bool:
        existing = {row[1] for row in db.execute(f'PRAGMA table_info("{table}")')}
        return columns.issubset(existing)

    def _select_dicts(self, db: sqlite3.Connection, sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
        return [dict(row) for row in db.execute(sql, params).fetchall()]

    def _insert_row(self, db: sqlite3.Connection, table: str, row: dict[str, Any]) -> None:
        columns = list(row.keys())
        quoted = ", ".join(f'"{column}"' for column in columns)
        marks = ", ".join("?" for _ in columns)
        values = [row[column] for column in columns]
        db.execute(f'INSERT OR REPLACE INTO "{table}" ({quoted}) VALUES ({marks})', values)
