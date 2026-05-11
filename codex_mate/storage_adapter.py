from __future__ import annotations

import base64
import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from codex_mate.backup_store import BackupStore
from codex_mate.models import DeleteResult, DeleteStatus, SessionRef


class SQLiteStorageAdapter:
    def __init__(self, db_path: Path, backup_store: BackupStore):
        self.db_path = db_path
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

        sidecar_errors = self._remove_codex_thread_sidecar_refs(thread_id)
        cleanup_errors = file_delete_errors + sidecar_errors
        if cleanup_errors:
            if file_delete_errors and not sidecar_errors:
                message = "本地数据库已删除，但文件删除失败：" + "; ".join(cleanup_errors)
            else:
                message = "本地数据库已删除，但清理索引/文件失败：" + "; ".join(cleanup_errors)
            return DeleteResult(DeleteStatus.FAILED, thread_id, message, undo_token=token, backup_path=str(self.backup_store.path_for(token)))

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
        sidecar_errors = self._remove_codex_thread_sidecar_refs(thread_id)
        cleanup_errors = file_delete_errors + sidecar_errors
        if cleanup_errors:
            return DeleteResult(DeleteStatus.FAILED, thread_id, "本地数据库无此会话，但清理残留索引/文件失败：" + "; ".join(cleanup_errors), undo_token=token, backup_path=str(self.backup_store.path_for(token)))
        return self._local_deleted(thread_id, token)

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
        sessions_dir = self.db_path.parent / "sessions"
        if not sessions_dir.exists():
            return []
        variants = self._codex_thread_id_variants(thread_id)
        matches = []
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
        for path in (self.db_path.parent / "session_index.jsonl", self.db_path.parent / ".codex-global-state.json"):
            if path.is_file():
                backups.append({"path": str(path), "content_b64": base64.b64encode(path.read_bytes()).decode("ascii")})
        return backups

    def _remove_codex_thread_sidecar_refs(self, thread_id: str) -> list[str]:
        errors = []
        for cleanup in (self._remove_thread_from_session_index, self._remove_thread_from_global_state):
            try:
                cleanup(thread_id)
            except OSError as exc:
                errors.append(str(exc))
        return errors

    def _codex_sidecar_refs_exist(self, thread_id: str) -> bool:
        variants = self._codex_thread_id_variants(thread_id)
        index_path = self.db_path.parent / "session_index.jsonl"
        if index_path.exists():
            for line in index_path.read_text(encoding="utf-8").splitlines():
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(item, dict) and str(item.get("id") or "") in variants:
                    return True
        global_state_path = self.db_path.parent / ".codex-global-state.json"
        if global_state_path.exists():
            try:
                state = json.loads(global_state_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return False
            return self._contains_thread_keys_or_list_values(state, variants)
        return False

    def _remove_thread_from_session_index(self, thread_id: str) -> None:
        path = self.db_path.parent / "session_index.jsonl"
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

    def _remove_thread_from_global_state(self, thread_id: str) -> None:
        path = self.db_path.parent / ".codex-global-state.json"
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
        if changed:
            self._atomic_write_text(path, json.dumps(cleaned, ensure_ascii=False, indent=2) + "\n")

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
                next_item, item_changed = self._remove_thread_keys_and_list_values(item, variants)
                cleaned_list.append(next_item)
                changed = changed or item_changed
            return cleaned_list, changed
        return value, False

    def _contains_thread_keys_or_list_values(self, value: Any, variants: set[str]) -> bool:
        if isinstance(value, dict):
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
