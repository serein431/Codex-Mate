from __future__ import annotations

import json
import shutil
import sqlite3
import time
import tomllib
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


UTC = timezone.utc


@dataclass(frozen=True)
class HistoryPaths:
    codex_home: Path
    config_path: Path
    db_path: Path
    sessions_dir: Path
    session_index_path: Path
    backup_dir: Path


@dataclass(frozen=True)
class CurrentProfile:
    provider: str
    model: str | None


def resolve_paths(codex_home: str | Path | None = None) -> HistoryPaths:
    home = Path(codex_home).expanduser() if codex_home is not None else Path.home() / ".codex"
    return HistoryPaths(
        codex_home=home,
        config_path=home / "config.toml",
        db_path=home / "state_5.sqlite",
        sessions_dir=home / "sessions",
        session_index_path=home / "session_index.jsonl",
        backup_dir=home / "codex_mate_history_backups",
    )


def environment_missing_reason(paths: HistoryPaths) -> str | None:
    missing = []
    if not paths.config_path.exists():
        missing.append(str(paths.config_path))
    if not paths.db_path.exists():
        missing.append(str(paths.db_path))
    if missing:
        return "missing " + ", ".join(missing)
    return None


def read_current_profile(paths: HistoryPaths) -> CurrentProfile:
    config = tomllib.loads(paths.config_path.read_text(encoding="utf-8"))
    provider = str(config.get("model_provider") or "").strip()
    if not provider:
        raise RuntimeError(f"Missing model_provider in {paths.config_path}")
    model = config.get("model")
    return CurrentProfile(provider=provider, model=str(model).strip() if model else None)


@contextmanager
def connect_db(path: Path, readonly: bool = False) -> Iterator[sqlite3.Connection]:
    if readonly:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=30.0)
    else:
        conn = sqlite3.connect(str(path), timeout=30.0)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 30000")
        yield conn
    finally:
        conn.close()


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table})")}


def backup_path(paths: HistoryPaths, label: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return paths.backup_dir / f"state_5.sqlite.{label}.{stamp}.bak"


def session_index_backup_path(db_backup: Path) -> Path:
    return db_backup.with_name(db_backup.name + ".session_index.jsonl")


def session_meta_backup_path(db_backup: Path) -> Path:
    return db_backup.with_name(db_backup.name + ".session_meta.json")


def make_backup(paths: HistoryPaths, label: str = "pre-sync") -> Path:
    paths.backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_path(paths, label)
    with connect_db(paths.db_path, readonly=True) as source, connect_db(target) as dest:
        source.backup(dest)
    if paths.session_index_path.exists():
        session_index_backup_path(target).write_text(paths.session_index_path.read_text(encoding="utf-8"), encoding="utf-8")
    session_meta_backup_path(target).write_text(
        json.dumps(snapshot_session_meta(paths), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target


def iter_session_files(paths: HistoryPaths) -> list[Path]:
    if not paths.sessions_dir.exists():
        return []
    return sorted(paths.sessions_dir.rglob("rollout-*.jsonl"))


def split_first_line(text: str) -> tuple[str, str, str]:
    for ending in ("\r\n", "\n", "\r"):
        index = text.find(ending)
        if index >= 0:
            return text[:index], ending, text[index + len(ending) :]
    return text, "", ""


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.codex-mate-{time.time_ns()}.tmp")
    try:
        temp.write_text(text, encoding="utf-8", newline="")
        temp.replace(path)
    finally:
        if temp.exists():
            temp.unlink()


def snapshot_session_meta(paths: HistoryPaths) -> list[dict[str, str]]:
    items = []
    for path in iter_session_files(paths):
        first_line, _, _ = split_first_line(path.read_text(encoding="utf-8"))
        if not first_line:
            continue
        try:
            relative = path.relative_to(paths.codex_home)
        except ValueError:
            relative = path
        items.append({"path": str(relative), "first_line": first_line})
    return items


def update_database_threads(paths: HistoryPaths, profile: CurrentProfile) -> dict[str, object]:
    with connect_db(paths.db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        columns = table_columns(conn, "threads")
        set_parts = ["model_provider = ?"]
        set_values: list[str] = [profile.provider]
        where_parts = ["model_provider IS NULL OR model_provider <> ?"]
        where_values: list[str] = [profile.provider]
        updated_fields = ["model_provider"]
        if "model" in columns and profile.model:
            set_parts.append("model = ?")
            set_values.append(profile.model)
            where_parts.append("model IS NULL OR model <> ?")
            where_values.append(profile.model)
            updated_fields.append("model")
        changed = conn.execute(
            f"UPDATE threads SET {', '.join(set_parts)} WHERE {' OR '.join(f'({part})' for part in where_parts)}",
            (*set_values, *where_values),
        ).rowcount
        conn.commit()
    return {"updated_database_rows": int(changed), "updated_fields": updated_fields}


def update_session_files(paths: HistoryPaths, profile: CurrentProfile) -> int:
    changed = 0
    for path in iter_session_files(paths):
        text = path.read_text(encoding="utf-8")
        first_line, ending, remainder = split_first_line(text)
        if not first_line:
            continue
        try:
            item = json.loads(first_line)
        except json.JSONDecodeError:
            continue
        if item.get("type") != "session_meta":
            continue
        payload = item.get("payload")
        if not isinstance(payload, dict):
            continue
        current_provider = str(payload.get("model_provider") or "")
        current_model = str(payload.get("model") or "") if payload.get("model") else None
        model_matches = profile.model is None or current_model == profile.model
        if current_provider == profile.provider and model_matches:
            continue
        payload["model_provider"] = profile.provider
        if profile.model:
            payload["model"] = profile.model
        new_first = json.dumps(item, ensure_ascii=False, separators=(",", ":"))
        atomic_write_text(path, new_first + (ending + remainder if ending else "\n"))
        changed += 1
    return changed


def iso_from_unix(value: int | None) -> str:
    if not value:
        return datetime.fromtimestamp(0, tz=UTC).isoformat().replace("+00:00", "Z")
    return datetime.fromtimestamp(int(value), tz=UTC).isoformat().replace("+00:00", "Z")


def read_existing_session_index(paths: HistoryPaths) -> list[dict[str, object]]:
    if not paths.session_index_path.exists():
        return []
    entries: list[dict[str, object]] = []
    for line in paths.session_index_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict):
            continue
        thread_id = entry.get("id")
        if isinstance(thread_id, str) and thread_id:
            entries.append(entry)
    return entries


def rebuild_session_index(paths: HistoryPaths) -> dict[str, int]:
    existing_entries = read_existing_session_index(paths)
    existing_by_id = {str(entry["id"]): entry for entry in existing_entries}
    with connect_db(paths.db_path, readonly=True) as conn:
        columns = table_columns(conn, "threads")
        select_parts = ["id"]
        if "title" in columns:
            select_parts.append("title")
        if "updated_at" in columns:
            select_parts.append("updated_at")
        where_sql = "WHERE archived = 0" if "archived" in columns else ""
        rows = conn.execute(
            f"SELECT {', '.join(select_parts)} FROM threads {where_sql} ORDER BY updated_at ASC, id ASC"
        ).fetchall()

    active_by_id: dict[str, dict[str, object]] = {}
    for row in rows:
        thread_id = str(row["id"])
        title = str(row["title"]) if "title" in row.keys() and row["title"] else str(row["id"])
        updated_at = int(row["updated_at"]) if "updated_at" in row.keys() and row["updated_at"] else 0
        active_by_id[thread_id] = {"id": thread_id, "thread_name": title, "updated_at": iso_from_unix(updated_at)}

    entries: list[dict[str, object]] = []
    seen: set[str] = set()
    for existing in existing_entries:
        thread_id = str(existing["id"])
        entry = dict(existing)
        if thread_id in active_by_id:
            entry.update(active_by_id[thread_id])
        entries.append(entry)
        seen.add(thread_id)

    for thread_id, active_entry in active_by_id.items():
        if thread_id in seen:
            continue
        entry = dict(existing_by_id.get(thread_id, {}))
        entry.update(active_entry)
        entries.append(entry)

    content = "".join(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n" for entry in entries)
    atomic_write_text(paths.session_index_path, content)
    return {"rewritten_index_entries": len(entries), "preserved_index_entries": len(existing_entries)}


def list_history_backups(paths: HistoryPaths) -> list[Path]:
    if not paths.backup_dir.exists():
        return []
    return sorted(paths.backup_dir.glob("state_5.sqlite.*.bak"), key=lambda path: path.stat().st_mtime)


def latest_history_backup(paths: HistoryPaths) -> Path:
    backups = list_history_backups(paths)
    if not backups:
        raise RuntimeError(f"No Codex Mate history backups found in {paths.backup_dir}")
    return backups[-1]


def restore_session_meta_snapshot(paths: HistoryPaths, meta_path: Path) -> int:
    if not meta_path.exists():
        return 0
    restored = 0
    items = json.loads(meta_path.read_text(encoding="utf-8"))
    if not isinstance(items, list):
        return 0
    for item in items:
        if not isinstance(item, dict):
            continue
        raw_path = item.get("path")
        first_line = item.get("first_line")
        if not isinstance(raw_path, str) or not isinstance(first_line, str):
            continue
        path = Path(raw_path)
        if not path.is_absolute():
            path = paths.codex_home / path
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        _, ending, remainder = split_first_line(text)
        atomic_write_text(path, first_line + (ending + remainder if ending else "\n"))
        restored += 1
    return restored


def restore_history_backup(paths: HistoryPaths, backup: str | Path | None = None) -> dict[str, object]:
    backup_path = Path(backup).expanduser() if backup is not None else latest_history_backup(paths)
    if not backup_path.exists():
        raise RuntimeError(f"Backup not found: {backup_path}")
    if backup_path.name.startswith(".") or backup_path.suffix != ".bak":
        raise RuntimeError(f"Invalid history backup path: {backup_path}")

    current_backup = make_backup(paths, label="pre-restore") if paths.db_path.exists() else None
    paths.db_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(backup_path, paths.db_path)

    index_path = session_index_backup_path(backup_path)
    restored_index = False
    if index_path.exists():
        paths.session_index_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(index_path, paths.session_index_path)
        restored_index = True

    restored_session_files = restore_session_meta_snapshot(paths, session_meta_backup_path(backup_path))
    return {
        "ok": True,
        "restored_backup_path": str(backup_path),
        "pre_restore_backup_path": str(current_backup) if current_backup else None,
        "restored_database": True,
        "restored_session_index": restored_index,
        "restored_session_files": restored_session_files,
    }


def sync_history_to_current_profile(paths: HistoryPaths) -> dict[str, object]:
    missing = environment_missing_reason(paths)
    if missing:
        raise RuntimeError(missing)
    profile = read_current_profile(paths)
    db_backup = make_backup(paths)
    db_result = update_database_threads(paths, profile)
    session_count = update_session_files(paths, profile)
    index_result = rebuild_session_index(paths)
    return {
        "ok": True,
        "skipped": False,
        "current_provider": profile.provider,
        "current_model": profile.model,
        "backup_path": str(db_backup),
        "updated_session_files": session_count,
        **db_result,
        **index_result,
    }


def sync_history_if_ready(paths: HistoryPaths) -> dict[str, object]:
    missing = environment_missing_reason(paths)
    if missing:
        return {"ok": True, "skipped": True, "reason": missing}
    return sync_history_to_current_profile(paths)


def status(paths: HistoryPaths) -> dict[str, object]:
    missing = environment_missing_reason(paths)
    if missing:
        return {"ok": True, "ready": False, "reason": missing}
    profile = read_current_profile(paths)
    with connect_db(paths.db_path, readonly=True) as conn:
        columns = table_columns(conn, "threads")
        total = int(conn.execute("SELECT COUNT(*) FROM threads").fetchone()[0])
        mismatched_provider = int(
            conn.execute(
                "SELECT COUNT(*) FROM threads WHERE model_provider IS NULL OR model_provider <> ?",
                (profile.provider,),
            ).fetchone()[0]
        )
        mismatched_model = None
        if "model" in columns and profile.model:
            mismatched_model = int(
                conn.execute(
                    "SELECT COUNT(*) FROM threads WHERE model IS NULL OR model <> ?",
                    (profile.model,),
                ).fetchone()[0]
            )
    return {
        "ok": True,
        "ready": True,
        "current_provider": profile.provider,
        "current_model": profile.model,
        "total_threads": total,
        "mismatched_provider_threads": mismatched_provider,
        "mismatched_model_threads": mismatched_model,
        "session_file_count": len(iter_session_files(paths)),
    }
