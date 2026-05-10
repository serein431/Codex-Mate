from __future__ import annotations

import base64
import sqlite3
from pathlib import Path
from typing import Any

from codex_session_delete.backup_store import BackupStore
from codex_session_delete.models import DeleteResult, DeleteStatus, SessionRef


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
            return DeleteResult(DeleteStatus.FAILED, session.session_id, "Thread not found in local storage")

        tables: dict[str, list[dict[str, Any]]] = {"threads": thread_rows}
        self._backup_related_rows(db, tables, "thread_dynamic_tools", "thread_id = ?", (thread_id,))
        self._backup_related_rows(db, tables, "thread_goals", "thread_id = ?", (thread_id,))
        self._backup_related_rows(db, tables, "thread_spawn_edges", "parent_thread_id = ? OR child_thread_id = ?", (thread_id, thread_id))
        self._backup_related_rows(db, tables, "stage1_outputs", "thread_id = ?", (thread_id,))
        self._backup_related_rows(db, tables, "agent_job_items", "assigned_thread_id = ?", (thread_id,))

        file_backups = self._rollout_file_backups(thread_rows)
        if file_backups:
            tables["__files"] = file_backups

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
        if file_delete_errors:
            return DeleteResult(DeleteStatus.FAILED, thread_id, "本地数据库已删除，但文件删除失败：" + "; ".join(file_delete_errors), undo_token=token, backup_path=str(self.backup_store.path_for(token)))

        return self._local_deleted(thread_id, token)

    def _normalize_codex_thread_id(self, session_id: str) -> str:
        return session_id.removeprefix("local:")

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

    def _rollout_file_backups(self, thread_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        file_backups = []
        for row in thread_rows:
            rollout_path = row.get("rollout_path")
            if not rollout_path:
                continue
            path = Path(str(rollout_path))
            if path.is_file():
                file_backups.append({"path": str(path), "content_b64": base64.b64encode(path.read_bytes()).decode("ascii")})
        return file_backups

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
