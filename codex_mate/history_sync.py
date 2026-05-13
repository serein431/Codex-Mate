from __future__ import annotations

import json
import sqlite3
import time
import tomllib
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


UTC = timezone.utc
DEFAULT_MODEL_PROVIDER = "openai"


@dataclass(frozen=True)
class HistoryPaths:
    codex_home: Path
    config_path: Path
    db_path: Path
    sessions_dir: Path
    session_index_path: Path
    global_state_path: Path
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
        global_state_path=home / ".codex-global-state.json",
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
    provider = str(config.get("model_provider") or DEFAULT_MODEL_PROVIDER).strip()
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


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone() is not None


def backup_path(paths: HistoryPaths, label: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return paths.backup_dir / f"state_5.sqlite.{label}.{stamp}.bak"


def session_index_backup_path(db_backup: Path) -> Path:
    return db_backup.with_name(db_backup.name + ".session_index.jsonl")


def session_meta_backup_path(db_backup: Path) -> Path:
    return db_backup.with_name(db_backup.name + ".session_meta.json")


def global_state_backup_path(db_backup: Path) -> Path:
    return db_backup.with_name(db_backup.name + ".codex-global-state.json")


def make_backup(paths: HistoryPaths, label: str = "pre-sync") -> Path:
    paths.backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_path(paths, label)
    with connect_db(paths.db_path, readonly=True) as source, connect_db(target) as dest:
        source.backup(dest)
    if paths.session_index_path.exists():
        session_index_backup_path(target).write_text(paths.session_index_path.read_text(encoding="utf-8"), encoding="utf-8")
    if paths.global_state_path.exists():
        global_state_backup_path(target).write_text(paths.global_state_path.read_text(encoding="utf-8"), encoding="utf-8")
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
        try:
            first_line, _, _ = split_first_line(path.read_text(encoding="utf-8"))
        except OSError:
            continue
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
        if not table_exists(conn, "threads"):
            return {"updated_database_rows": 0, "updated_fields": [], "skipped_database_sync": "missing threads table"}
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


def update_session_files(paths: HistoryPaths, profile: CurrentProfile) -> dict[str, object]:
    changed = 0
    skipped: list[str] = []
    for path in iter_session_files(paths):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            skipped.append(f"{path}: {exc}")
            continue
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
        try:
            atomic_write_text(path, new_first + (ending + remainder if ending else "\n"))
        except OSError as exc:
            skipped.append(f"{path}: {exc}")
            continue
        changed += 1
    return {"updated_session_files": changed, "skipped_session_files": skipped}


def iso_from_unix(value: int | None) -> str:
    if not value:
        return datetime.fromtimestamp(0, tz=UTC).isoformat().replace("+00:00", "Z")
    return datetime.fromtimestamp(int(value), tz=UTC).isoformat().replace("+00:00", "Z")


def read_session_index_entries(paths: HistoryPaths) -> list[dict[str, object]]:
    if not paths.session_index_path.exists():
        return []
    entries = []
    for line in paths.session_index_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict) and item.get("id"):
            entries.append(item)
    return entries


def session_file_thread_ids(paths: HistoryPaths) -> set[str]:
    ids: set[str] = set()
    for path in iter_session_files(paths):
        try:
            first_line, _, _ = split_first_line(path.read_text(encoding="utf-8"))
        except OSError:
            continue
        if not first_line:
            continue
        try:
            item = json.loads(first_line)
        except json.JSONDecodeError:
            continue
        payload = item.get("payload")
        if item.get("type") == "session_meta" and isinstance(payload, dict) and payload.get("id"):
            ids.add(str(payload["id"]))
    return ids


def active_thread_index_entries(paths: HistoryPaths) -> list[dict[str, object]]:
    with connect_db(paths.db_path, readonly=True) as conn:
        if not table_exists(conn, "threads"):
            return []
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

    entries = []
    for row in rows:
        title = str(row["title"]) if "title" in row.keys() and row["title"] else str(row["id"])
        updated_at = int(row["updated_at"]) if "updated_at" in row.keys() and row["updated_at"] else 0
        entries.append(
            {
                "id": str(row["id"]),
                "thread_name": title,
                "updated_at": iso_from_unix(updated_at),
            }
        )
    return entries


def active_thread_ui_entries(paths: HistoryPaths) -> list[dict[str, object]]:
    with connect_db(paths.db_path, readonly=True) as conn:
        if not table_exists(conn, "threads"):
            return []
        columns = table_columns(conn, "threads")
        select_parts = ["id"]
        if "cwd" in columns:
            select_parts.append("cwd")
        if "updated_at" in columns:
            select_parts.append("updated_at")
        if "updated_at_ms" in columns:
            select_parts.append("updated_at_ms")
        where_sql = "WHERE archived = 0" if "archived" in columns else ""
        order_terms = []
        if "updated_at_ms" in columns:
            order_terms.append("updated_at_ms")
        if "updated_at" in columns:
            order_terms.append("updated_at * 1000")
        order_sql = f"ORDER BY COALESCE({', '.join(order_terms)}, 0) DESC, id ASC" if order_terms else "ORDER BY id ASC"
        rows = conn.execute(f"SELECT {', '.join(select_parts)} FROM threads {where_sql} {order_sql}").fetchall()

    entries = []
    for row in rows:
        entries.append(
            {
                "id": str(row["id"]),
                "cwd": str(row["cwd"] or "") if "cwd" in row.keys() else "",
            }
        )
    return entries


def merge_session_index(paths: HistoryPaths) -> dict[str, int]:
    db_entries = active_thread_index_entries(paths)
    existing_entries = read_session_index_entries(paths)
    existing_by_id = {str(entry["id"]): entry for entry in existing_entries}
    file_thread_ids = session_file_thread_ids(paths)

    merged: list[dict[str, object]] = []
    seen: set[str] = set()
    for entry in db_entries:
        entry_id = str(entry["id"])
        existing = existing_by_id.get(entry_id, {})
        merged.append({**existing, **entry})
        seen.add(entry_id)
    for entry in existing_entries:
        entry_id = str(entry["id"])
        if entry_id not in seen and entry_id in file_thread_ids:
            merged.append(entry)
            seen.add(entry_id)

    if not merged and existing_entries:
        merged = existing_entries
    if merged:
        content = "".join(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n" for entry in merged)
        try:
            atomic_write_text(paths.session_index_path, content)
        except OSError as exc:
            return {
                "rewritten_index_entries": len(existing_entries),
                "database_index_entries": len(db_entries),
                "preserved_index_entries": len(existing_entries),
                "skipped_session_index": str(exc),
            }
    return {"rewritten_index_entries": len(merged), "database_index_entries": len(db_entries), "preserved_index_entries": len(merged) - len(db_entries)}


def load_global_state(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def ensure_list(value: object) -> list[object]:
    return list(value) if isinstance(value, list) else []


def ensure_dict(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, dict) else {}


def append_missing(values: list[object], candidates: list[str]) -> tuple[list[object], int]:
    seen = {str(value) for value in values if isinstance(value, str)}
    changed = 0
    result = list(values)
    for candidate in candidates:
        if candidate and candidate not in seen:
            result.append(candidate)
            seen.add(candidate)
            changed += 1
    return result, changed


def remove_strings(values: list[object], removals: set[str]) -> tuple[list[object], int]:
    changed = 0
    result: list[object] = []
    for value in values:
        if isinstance(value, str) and value in removals:
            changed += 1
            continue
        result.append(value)
    return result, changed


def sync_global_state(paths: HistoryPaths) -> dict[str, object]:
    entries = active_thread_ui_entries(paths)
    if not entries:
        return {
            "updated_global_state": False,
            "global_state_thread_hints_added": 0,
            "global_state_project_roots_added": 0,
            "global_state_projectless_threads_added": 0,
            "global_state_projectless_threads_removed": 0,
        }

    state = load_global_state(paths.global_state_path)
    hints = ensure_dict(state.get("thread-workspace-root-hints"))
    project_order = ensure_list(state.get("project-order"))
    saved_roots = ensure_list(state.get("electron-saved-workspace-roots"))
    projectless_thread_ids = ensure_list(state.get("projectless-thread-ids"))

    hint_changes = 0
    projectless_candidates: list[str] = []
    project_thread_ids: set[str] = set()
    for entry in entries:
        thread_id = str(entry["id"])
        cwd = str(entry.get("cwd") or "")
        if cwd:
            project_thread_ids.add(thread_id)
            if hints.get(thread_id) != cwd:
                hints[thread_id] = cwd
                hint_changes += 1
        else:
            projectless_candidates.append(thread_id)

    project_order_changes = 0
    saved_root_changes = 0
    projectless_thread_ids, projectless_removed = remove_strings(projectless_thread_ids, project_thread_ids)
    projectless_thread_ids, projectless_changes = append_missing(projectless_thread_ids, projectless_candidates)

    changed = hint_changes + project_order_changes + saved_root_changes + projectless_removed + projectless_changes
    if changed:
        state["thread-workspace-root-hints"] = hints
        state["project-order"] = project_order
        state["electron-saved-workspace-roots"] = saved_roots
        state["projectless-thread-ids"] = projectless_thread_ids
        atomic_write_text(paths.global_state_path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")

    return {
        "updated_global_state": bool(changed),
        "global_state_thread_hints_added": hint_changes,
        "global_state_project_roots_added": project_order_changes,
        "global_state_saved_roots_added": saved_root_changes,
        "global_state_projectless_threads_added": projectless_changes,
        "global_state_projectless_threads_removed": projectless_removed,
    }


def sync_history_to_current_profile(paths: HistoryPaths) -> dict[str, object]:
    missing = environment_missing_reason(paths)
    if missing:
        raise RuntimeError(missing)
    profile = read_current_profile(paths)
    db_backup = make_backup(paths)
    db_result = update_database_threads(paths, profile)
    session_result = update_session_files(paths, profile)
    index_result = merge_session_index(paths)
    global_state_result = sync_global_state(paths)
    return {
        "ok": True,
        "skipped": False,
        "current_provider": profile.provider,
        "current_model": profile.model,
        "backup_path": str(db_backup),
        **db_result,
        **session_result,
        **index_result,
        **global_state_result,
    }


def sync_history_if_ready(paths: HistoryPaths) -> dict[str, object]:
    missing = environment_missing_reason(paths)
    if missing:
        return {"ok": True, "skipped": True, "reason": missing}
    current_status = status(paths)
    mismatched_provider = int(current_status.get("mismatched_provider_threads") or 0)
    mismatched_model = int(current_status.get("mismatched_model_threads") or 0)
    if mismatched_provider == 0 and mismatched_model == 0:
        return {
            **current_status,
            "skipped": True,
            "reason": "history already matches current provider/model",
        }
    return sync_history_to_current_profile(paths)


def status(paths: HistoryPaths) -> dict[str, object]:
    missing = environment_missing_reason(paths)
    if missing:
        return {"ok": True, "ready": False, "reason": missing}
    profile = read_current_profile(paths)
    with connect_db(paths.db_path, readonly=True) as conn:
        if not table_exists(conn, "threads"):
            return {
                "ok": True,
                "ready": True,
                "current_provider": profile.provider,
                "current_model": profile.model,
                "total_threads": 0,
                "mismatched_provider_threads": 0,
                "mismatched_model_threads": None,
                "session_file_count": len(iter_session_files(paths)),
                "session_index_count": len(read_session_index_entries(paths)),
                "skipped_database_status": "missing threads table",
            }
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
        "session_index_count": len(read_session_index_entries(paths)),
    }
