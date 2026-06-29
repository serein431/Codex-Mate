from __future__ import annotations

import json
import os
import shutil
import sqlite3
import time
import tomllib
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import TracebackType
from typing import Iterator

from codex_mate import codex_storage


UTC = timezone.utc
DEFAULT_MODEL_PROVIDER = "openai"


@dataclass(frozen=True)
class HistoryPaths:
    codex_home: Path
    config_path: Path
    db_path: Path
    db_paths: tuple[Path, ...]
    sessions_dir: Path
    session_dirs: tuple[Path, ...]
    session_index_path: Path
    global_state_path: Path
    backup_dir: Path


@dataclass(frozen=True)
class CurrentProfile:
    provider: str
    model: str | None


@dataclass(frozen=True)
class SessionMetadata:
    thread_id: str | None
    provider: str | None
    model: str | None
    missing_provider: bool


@dataclass(frozen=True)
class ProviderSyncSessionChange:
    path: Path
    original_text: str
    next_text: str
    original_mtime_ns: int | None
    thread_id: str | None
    cwd: str | None
    has_user_event: bool
    rewrite_needed: bool
    encrypted_provider_warning: bool


class ProviderSyncLock:
    def __init__(self, path: Path):
        self.path = path
        self.acquired = False

    def __enter__(self) -> "ProviderSyncLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.path.mkdir()
        except FileExistsError as exc:
            raise RuntimeError(f"provider sync lock exists: {self.path}") from exc
        self.acquired = True
        owner = {"pid": os.getpid(), "started_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
        try:
            (self.path / "owner.json").write_text(json.dumps(owner, ensure_ascii=False) + "\n", encoding="utf-8")
        except OSError:
            pass
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self.acquired:
            shutil.rmtree(self.path, ignore_errors=True)

def resolve_paths(codex_home: str | Path | None = None) -> HistoryPaths:
    home = Path(codex_home).expanduser() if codex_home is not None else Path.home() / ".codex"
    discovered = tuple(codex_storage.discover_thread_db_paths(home))
    primary = discovered[0] if discovered else codex_storage.primary_thread_db_path(home)
    db_paths = discovered or ((primary,) if primary.exists() else tuple())
    sessions_dir = home / "sessions"
    session_dirs = tuple(codex_storage.rollout_dirs(home))
    return HistoryPaths(
        codex_home=home,
        config_path=home / "config.toml",
        db_path=primary,
        db_paths=db_paths,
        sessions_dir=sessions_dir,
        session_dirs=session_dirs,
        session_index_path=home / "session_index.jsonl",
        global_state_path=home / ".codex-global-state.json",
        backup_dir=home / "codex_mate_history_backups",
    )


def environment_missing_reason(paths: HistoryPaths) -> str | None:
    missing = []
    if not paths.config_path.exists():
        missing.append(str(paths.config_path))
    if not paths.db_paths and not paths.db_path.exists():
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


def database_paths(paths: HistoryPaths) -> tuple[Path, ...]:
    if paths.db_paths:
        return paths.db_paths
    return (paths.db_path,) if paths.db_path.exists() else tuple()


def extra_database_backup_path(paths: HistoryPaths, primary_backup: Path, db_path: Path) -> Path:
    try:
        relative = db_path.relative_to(paths.codex_home)
    except ValueError:
        relative = db_path.name
    safe = str(relative).replace("/", "__").replace("\\", "__")
    return primary_backup.with_name(f"{primary_backup.name}.{safe}.bak")


def session_index_backup_path(db_backup: Path) -> Path:
    return db_backup.with_name(db_backup.name + ".session_index.jsonl")


def session_meta_backup_path(db_backup: Path) -> Path:
    return db_backup.with_name(db_backup.name + ".session_meta.json")


def global_state_backup_path(db_backup: Path) -> Path:
    return db_backup.with_name(db_backup.name + ".codex-global-state.json")


def make_backup(paths: HistoryPaths, label: str = "pre-sync") -> tuple[Path, list[Path]]:
    paths.backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_path(paths, label)
    backed_up: list[Path] = []
    for index, db_path in enumerate(database_paths(paths)):
        backup_target = target if index == 0 else extra_database_backup_path(paths, target, db_path)
        with connect_db(db_path, readonly=True) as source, connect_db(backup_target) as dest:
            source.backup(dest)
        backed_up.append(backup_target)
    if paths.session_index_path.exists():
        session_index_backup_path(target).write_text(paths.session_index_path.read_text(encoding="utf-8"), encoding="utf-8")
    if paths.global_state_path.exists():
        global_state_backup_path(target).write_text(paths.global_state_path.read_text(encoding="utf-8"), encoding="utf-8")
    session_meta_backup_path(target).write_text(
        json.dumps(snapshot_session_meta(paths), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target, backed_up


def iter_session_files(paths: HistoryPaths) -> list[Path]:
    seen: set[Path] = set()
    files: list[Path] = []
    dirs = paths.session_dirs or ((paths.sessions_dir,) if paths.sessions_dir.exists() else tuple())
    for directory in dirs:
        if not directory.exists():
            continue
        for path in sorted(directory.rglob("rollout-*.jsonl")):
            if path in seen:
                continue
            seen.add(path)
            files.append(path)
    return files


def split_first_line(text: str) -> tuple[str, str, str]:
    for ending in ("\r\n", "\n", "\r"):
        index = text.find(ending)
        if index >= 0:
            return text[:index], ending, text[index + len(ending) :]
    return text, "", ""


def split_line_ending(line: str) -> tuple[str, str]:
    for ending in ("\r\n", "\n", "\r"):
        if line.endswith(ending):
            return line[: -len(ending)], ending
    return line, ""


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


def metadata_model_matches(current_model: str | None, profile: CurrentProfile) -> bool:
    return profile.model is None or current_model == profile.model


def metadata_matches_profile(provider: str | None, model: str | None, profile: CurrentProfile) -> bool:
    return provider == profile.provider and metadata_model_matches(model, profile)


def session_metadata_from_item(item: object, *, first_line: bool = False) -> SessionMetadata | None:
    if not isinstance(item, dict):
        return None
    if item.get("type") == "session_meta":
        payload = item.get("payload")
        if not isinstance(payload, dict):
            return None
        provider = str(payload.get("model_provider") or "") or None
        model = str(payload.get("model") or "") if payload.get("model") else None
        thread_id = str(payload.get("id")) if payload.get("id") else None
        return SessionMetadata(
            thread_id=thread_id,
            provider=provider,
            model=model,
            missing_provider=provider is None,
        )
    if first_line and item.get("id") and "type" not in item:
        provider = str(item.get("model_provider") or "") or None
        model = str(item.get("model") or "") if item.get("model") else None
        return SessionMetadata(
            thread_id=str(item["id"]),
            provider=provider,
            model=model,
            missing_provider=provider is None,
        )
    return None


def session_file_metadata(path: Path) -> list[SessionMetadata]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    items = []
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        metadata = session_metadata_from_item(item, first_line=index == 0)
        if metadata is not None:
            items.append(metadata)
    return items


def session_profile_status(paths: HistoryPaths, profile: CurrentProfile, thread_ids: set[str]) -> dict[str, int]:
    mismatched_session_files = 0
    mismatched_provider_files = 0
    missing_provider_files = 0
    mismatched_model_files = 0
    inspected_session_files = 0
    for path in iter_session_files(paths):
        records = [record for record in session_file_metadata(path) if record.thread_id in thread_ids]
        if not records:
            continue
        inspected_session_files += 1
        file_mismatched = False
        file_provider_mismatched = False
        file_missing_provider = False
        file_model_mismatched = False
        for record in records:
            provider_mismatched = record.provider != profile.provider
            model_mismatched = not metadata_model_matches(record.model, profile)
            file_mismatched = file_mismatched or provider_mismatched or model_mismatched
            file_provider_mismatched = file_provider_mismatched or provider_mismatched
            file_missing_provider = file_missing_provider or record.missing_provider
            file_model_mismatched = file_model_mismatched or model_mismatched
        if file_mismatched:
            mismatched_session_files += 1
        if file_provider_mismatched:
            mismatched_provider_files += 1
        if file_missing_provider:
            missing_provider_files += 1
        if file_model_mismatched:
            mismatched_model_files += 1
    return {
        "inspected_session_files": inspected_session_files,
        "mismatched_session_files": mismatched_session_files,
        "mismatched_session_provider_files": mismatched_provider_files,
        "session_files_missing_provider": missing_provider_files,
        "mismatched_session_model_files": mismatched_model_files,
    }


def update_database_threads(paths: HistoryPaths, profile: CurrentProfile) -> dict[str, object]:
    total_changed = 0
    changed_files = 0
    skipped: list[str] = []
    updated_fields: list[str] = []
    for db_path in database_paths(paths):
        with connect_db(db_path) as conn:
            if not table_exists(conn, "threads"):
                skipped.append(f"{db_path}: missing threads table")
                continue
            columns = table_columns(conn, "threads")
            if "model_provider" not in columns:
                skipped.append(f"{db_path}: missing model_provider column")
                continue
            conn.execute("BEGIN IMMEDIATE")
            fields = ["model_provider"]
            set_parts = ["model_provider = ?"]
            set_values: list[str] = [profile.provider]
            where_parts = ["model_provider IS NULL OR model_provider <> ?"]
            where_values: list[str] = [profile.provider]
            if "model" in columns and profile.model:
                set_parts.append("model = ?")
                set_values.append(profile.model)
                where_parts.append("model IS NULL OR model <> ?")
                where_values.append(profile.model)
                fields.append("model")
            changed = conn.execute(
                f"UPDATE threads SET {', '.join(set_parts)} WHERE {' OR '.join(f'({part})' for part in where_parts)}",
                (*set_values, *where_values),
            ).rowcount
            conn.commit()
        if changed:
            total_changed += int(changed)
            changed_files += 1
        for field in fields:
            if field not in updated_fields:
                updated_fields.append(field)
    result: dict[str, object] = {
        "updated_database_rows": total_changed,
        "updated_database_files": changed_files,
        "updated_fields": updated_fields,
    }
    if skipped:
        result["skipped_database_sync"] = skipped
    return result


def repair_database_thread_timestamps(paths: HistoryPaths) -> dict[str, object]:
    total_updates = 0
    changed_files = 0
    skipped: list[str] = []
    for db_path in database_paths(paths):
        with connect_db(db_path) as conn:
            if not table_exists(conn, "threads"):
                skipped.append(f"{db_path}: missing threads table")
                continue
            columns = table_columns(conn, "threads")
            required = {"id", "rollout_path", "updated_at", "updated_at_ms"}
            if not required.issubset(columns):
                skipped.append(f"{db_path}: missing timestamp columns")
                continue
            rows = conn.execute("SELECT id, rollout_path, updated_at, updated_at_ms FROM threads").fetchall()
            updates: list[tuple[int, int, str]] = []
            for row in rows:
                rollout_path = row["rollout_path"]
                if not rollout_path:
                    continue
                latest_timestamp = latest_session_timestamp_ms(Path(str(rollout_path)))
                if latest_timestamp is None:
                    continue
                current_ms = int(row["updated_at_ms"] or 0)
                if latest_timestamp > current_ms:
                    updates.append((latest_timestamp // 1000, latest_timestamp, str(row["id"])))
            if not updates:
                continue
            conn.execute("BEGIN IMMEDIATE")
            conn.executemany("UPDATE threads SET updated_at = ?, updated_at_ms = ? WHERE id = ?", updates)
            conn.commit()
        total_updates += len(updates)
        changed_files += 1
    result: dict[str, object] = {
        "updated_database_timestamps": total_updates,
        "updated_database_timestamp_files": changed_files,
    }
    if skipped:
        result["skipped_database_timestamp_repair"] = skipped
    return result


def update_session_files(paths: HistoryPaths, profile: CurrentProfile) -> dict[str, object]:
    changed = 0
    skipped: list[str] = []
    for path in iter_session_files(paths):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            skipped.append(f"{path}: {exc}")
            continue
        lines = text.splitlines(keepends=True)
        new_lines: list[str] = []
        file_changed = False
        for index, line in enumerate(lines):
            content, ending = split_line_ending(line)
            if not content:
                new_lines.append(line)
                continue
            try:
                item = json.loads(content)
            except json.JSONDecodeError:
                new_lines.append(line)
                continue
            if item.get("type") == "session_meta":
                payload = item.get("payload")
                if not isinstance(payload, dict):
                    new_lines.append(line)
                    continue
                current_provider = str(payload.get("model_provider") or "") or None
                current_model = str(payload.get("model") or "") if payload.get("model") else None
                if metadata_matches_profile(current_provider, current_model, profile):
                    new_lines.append(line)
                    continue
                payload["model_provider"] = profile.provider
                if profile.model:
                    payload["model"] = profile.model
                new_lines.append(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + ending)
                file_changed = True
                continue
            if not (index == 0 and isinstance(item, dict) and item.get("id") and "type" not in item):
                new_lines.append(line)
                continue
            current_provider = str(item.get("model_provider") or "") or None
            current_model = str(item.get("model") or "") if item.get("model") else None
            if metadata_matches_profile(current_provider, current_model, profile):
                new_lines.append(line)
                continue
            item["model_provider"] = profile.provider
            if profile.model:
                item["model"] = profile.model
            new_lines.append(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + ending)
            file_changed = True
        if not file_changed:
            continue
        try:
            atomic_write_text(path, "".join(new_lines))
        except OSError as exc:
            skipped.append(f"{path}: {exc}")
            continue
        changed += 1
    return {"updated_session_files": changed, "skipped_session_files": skipped}


def provider_sync_lock_path(paths: HistoryPaths) -> Path:
    return paths.codex_home / "tmp" / "provider-sync.lock"


def restore_file_mtime_ns(path: Path, mtime_ns: int | None) -> None:
    if mtime_ns is None:
        return
    try:
        os.utime(path, ns=(mtime_ns, mtime_ns))
    except OSError:
        pass


def provider_sync_line_payload(item: object, *, first_line: bool = False) -> dict[str, object] | None:
    if not isinstance(item, dict):
        return None
    if item.get("type") == "session_meta":
        payload = item.get("payload")
        return payload if isinstance(payload, dict) else None
    if first_line and item.get("id") and "type" not in item:
        return item
    return None


def rollout_has_user_event(text: str) -> bool:
    return '"user_message"' in text or '"user_input"' in text or '"role":"user"' in text or '"role": "user"' in text


def provider_sync_rollout_change(path: Path, profile: CurrentProfile) -> ProviderSyncSessionChange | None:
    try:
        text = path.read_text(encoding="utf-8")
        original_mtime_ns = path.stat().st_mtime_ns
    except OSError:
        return None
    new_lines: list[str] = []
    rewrite_needed = False
    thread_id: str | None = None
    cwd: str | None = None
    encrypted_provider_warning = False
    encrypted_present = "encrypted_content" in text
    for index, line in enumerate(text.splitlines(keepends=True)):
        content, ending = split_line_ending(line)
        if not content:
            new_lines.append(line)
            continue
        try:
            item = json.loads(content)
        except json.JSONDecodeError:
            new_lines.append(line)
            continue
        payload = provider_sync_line_payload(item, first_line=index == 0)
        if payload is None:
            new_lines.append(line)
            continue
        if thread_id is None and payload.get("id"):
            thread_id = str(payload.get("id"))
        if cwd is None and isinstance(payload.get("cwd"), str) and str(payload.get("cwd")).strip():
            cwd = str(payload.get("cwd")).strip()
        current_provider = payload.get("model_provider")
        if encrypted_present and current_provider != profile.provider:
            encrypted_provider_warning = True
        if current_provider != profile.provider:
            payload["model_provider"] = profile.provider
            rewrite_needed = True
        new_lines.append(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + ending)
    if not thread_id and not rewrite_needed and not encrypted_provider_warning:
        return None
    return ProviderSyncSessionChange(
        path=path,
        original_text=text,
        next_text="".join(new_lines),
        original_mtime_ns=original_mtime_ns,
        thread_id=thread_id,
        cwd=cwd,
        has_user_event=rollout_has_user_event(text),
        rewrite_needed=rewrite_needed,
        encrypted_provider_warning=encrypted_provider_warning,
    )


def collect_provider_sync_session_changes(paths: HistoryPaths, profile: CurrentProfile) -> list[ProviderSyncSessionChange]:
    changes: list[ProviderSyncSessionChange] = []
    for path in iter_session_files(paths):
        change = provider_sync_rollout_change(path, profile)
        if change is not None:
            changes.append(change)
    return changes


def write_provider_sync_session_changes(changes: list[ProviderSyncSessionChange]) -> tuple[list[ProviderSyncSessionChange], list[str]]:
    written: list[ProviderSyncSessionChange] = []
    skipped: list[str] = []
    for change in changes:
        if not change.rewrite_needed:
            continue
        try:
            atomic_write_text(change.path, change.next_text)
            restore_file_mtime_ns(change.path, change.original_mtime_ns)
            written.append(change)
        except OSError as exc:
            skipped.append(f"{change.path}: {exc}")
    return written, skipped


def restore_provider_sync_session_changes(changes: list[ProviderSyncSessionChange]) -> None:
    for change in changes:
        try:
            atomic_write_text(change.path, change.original_text)
            restore_file_mtime_ns(change.path, change.original_mtime_ns)
        except OSError:
            continue


def provider_sync_thread_metadata(changes: list[ProviderSyncSessionChange]) -> tuple[set[str], dict[str, str]]:
    user_event_thread_ids = {change.thread_id for change in changes if change.thread_id and change.has_user_event}
    cwd_by_thread_id = {change.thread_id: change.cwd for change in changes if change.thread_id and change.cwd}
    return set(user_event_thread_ids), dict(cwd_by_thread_id)


def update_provider_visibility_database_threads(
    paths: HistoryPaths,
    profile: CurrentProfile,
    changes: list[ProviderSyncSessionChange],
) -> dict[str, object]:
    total_changed = 0
    changed_files = 0
    skipped: list[str] = []
    updated_fields: list[str] = []
    user_event_thread_ids, cwd_by_thread_id = provider_sync_thread_metadata(changes)
    for db_path in database_paths(paths):
        with connect_db(db_path) as conn:
            if not table_exists(conn, "threads"):
                skipped.append(f"{db_path}: missing threads table")
                continue
            columns = table_columns(conn, "threads")
            if "model_provider" not in columns:
                skipped.append(f"{db_path}: missing model_provider column")
                continue
            conn.execute("BEGIN IMMEDIATE")
            file_changed = 0
            try:
                file_changed += conn.execute(
                    "UPDATE threads SET model_provider = ? WHERE model_provider IS NULL OR model_provider <> ?",
                    (profile.provider, profile.provider),
                ).rowcount
                if "model_provider" not in updated_fields:
                    updated_fields.append("model_provider")
                if "has_user_event" in columns and user_event_thread_ids:
                    for thread_id in sorted(user_event_thread_ids):
                        file_changed += conn.execute(
                            "UPDATE threads SET has_user_event = 1 WHERE id = ? AND COALESCE(has_user_event, 0) <> 1",
                            (thread_id,),
                        ).rowcount
                    if "has_user_event" not in updated_fields:
                        updated_fields.append("has_user_event")
                if "cwd" in columns and cwd_by_thread_id:
                    for thread_id, cwd in sorted(cwd_by_thread_id.items()):
                        file_changed += conn.execute(
                            "UPDATE threads SET cwd = ? WHERE id = ? AND COALESCE(cwd, '') <> ?",
                            (cwd, thread_id, cwd),
                        ).rowcount
                    if "cwd" not in updated_fields:
                        updated_fields.append("cwd")
            except sqlite3.Error:
                conn.rollback()
                raise
            else:
                conn.commit()
        if file_changed:
            total_changed += int(file_changed)
            changed_files += 1
    result: dict[str, object] = {
        "updated_database_rows": total_changed,
        "updated_database_files": changed_files,
        "updated_fields": updated_fields,
    }
    if skipped:
        result["skipped_database_sync"] = skipped
    return result


def iso_from_unix(value: int | None) -> str:
    if not value:
        return datetime.fromtimestamp(0, tz=UTC).isoformat().replace("+00:00", "Z")
    return datetime.fromtimestamp(int(value), tz=UTC).isoformat().replace("+00:00", "Z")


def iso_from_unix_ms(value: int | None) -> str:
    if not value:
        return iso_from_unix(None)
    return datetime.fromtimestamp(int(value) / 1000, tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_timestamp_ms(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int | float):
        number = float(value)
        if number <= 0:
            return None
        return int(number if number > 10_000_000_000 else number * 1000)
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.replace(".", "", 1).isdigit():
        return parse_timestamp_ms(float(text))
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return int(parsed.timestamp() * 1000)


def item_timestamp_ms(item: object) -> int | None:
    if not isinstance(item, dict):
        return None
    timestamp = parse_timestamp_ms(item.get("timestamp"))
    if timestamp is not None:
        return timestamp
    payload = item.get("payload")
    if isinstance(payload, dict):
        return parse_timestamp_ms(payload.get("timestamp"))
    return None


def latest_session_timestamp_ms(path: Path) -> int | None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        try:
            timestamp = item_timestamp_ms(json.loads(line))
        except json.JSONDecodeError:
            continue
        if timestamp is not None:
            return timestamp
    return None


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
        for metadata in session_file_metadata(path):
            if metadata.thread_id:
                ids.add(metadata.thread_id)
    return ids


def select_thread_rows(paths: HistoryPaths, columns: list[str], *, active_only: bool) -> list[dict[str, object]]:
    rows_by_id: dict[str, dict[str, object]] = {}
    for db_path in database_paths(paths):
        with connect_db(db_path, readonly=True) as conn:
            if not table_exists(conn, "threads"):
                continue
            existing = table_columns(conn, "threads")
            if "id" not in existing:
                continue
            select_parts = ["id", *(column for column in columns if column in existing)]
            where_sql = "WHERE archived = 0" if active_only and "archived" in existing else ""
            rows = conn.execute(f"SELECT {', '.join(select_parts)} FROM threads {where_sql}").fetchall()
        for row in rows:
            thread_id = str(row["id"])
            if thread_id not in rows_by_id:
                rows_by_id[thread_id] = dict(row)
    return list(rows_by_id.values())


def thread_row_sort_ms(row: dict[str, object]) -> int:
    rollout_path = str(row.get("rollout_path") or "")
    if rollout_path:
        rollout_ms = latest_session_timestamp_ms(Path(rollout_path))
        if rollout_ms is not None:
            return rollout_ms
    for key in ("updated_at_ms", "updated_at", "created_at_ms"):
        value = row.get(key)
        parsed = parse_timestamp_ms(value)
        if parsed is not None:
            return parsed
    return 0


def active_thread_index_entries(paths: HistoryPaths) -> list[dict[str, object]]:
    rows = select_thread_rows(paths, ["title", "rollout_path", "updated_at", "updated_at_ms", "created_at_ms"], active_only=True)
    rows.sort(key=lambda row: (thread_row_sort_ms(row), str(row["id"])))
    entries = []
    for row in rows:
        title = str(row.get("title") or row["id"])
        index_updated_at_ms = thread_row_sort_ms(row)
        updated_at = parse_timestamp_ms(row.get("updated_at"))
        entries.append(
            {
                "id": str(row["id"]),
                "thread_name": title,
                "updated_at": iso_from_unix_ms(index_updated_at_ms) if index_updated_at_ms is not None else iso_from_unix(updated_at),
            }
        )
    return entries


def active_thread_ui_entries(paths: HistoryPaths) -> list[dict[str, object]]:
    rows = select_thread_rows(paths, ["cwd", "updated_at", "updated_at_ms", "created_at_ms"], active_only=True)
    rows.sort(key=lambda row: (-thread_row_sort_ms(row), str(row["id"])))
    entries = []
    for row in rows:
        entries.append(
            {
                "id": str(row["id"]),
                "cwd": str(row.get("cwd") or ""),
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
        merged_entry = {**existing, **entry}
        existing_thread_name = existing.get("thread_name")
        if isinstance(existing_thread_name, str) and existing_thread_name.strip():
            merged_entry["thread_name"] = existing_thread_name
        existing_updated_at = existing.get("updated_at")
        if isinstance(existing_updated_at, str) and existing_updated_at.strip():
            merged_entry["updated_at"] = existing_updated_at
        merged.append(merged_entry)
        seen.add(entry_id)
    for entry in existing_entries:
        entry_id = str(entry["id"])
        if entry_id not in seen and entry_id in file_thread_ids:
            merged.append(entry)
            seen.add(entry_id)

    if not merged and existing_entries:
        merged = existing_entries
    updated_session_index = False
    if merged:
        content = "".join(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n" for entry in merged)
        existing_content = paths.session_index_path.read_text(encoding="utf-8") if paths.session_index_path.exists() else ""
        if content == existing_content:
            return {
                "rewritten_index_entries": len(merged),
                "database_index_entries": len(db_entries),
                "preserved_index_entries": len(merged) - len(db_entries),
                "updated_session_index": False,
            }
        try:
            atomic_write_text(paths.session_index_path, content)
            updated_session_index = True
        except OSError as exc:
            return {
                "rewritten_index_entries": len(existing_entries),
                "database_index_entries": len(db_entries),
                "preserved_index_entries": len(existing_entries),
                "skipped_session_index": str(exc),
                "updated_session_index": False,
            }
    return {
        "rewritten_index_entries": len(merged),
        "database_index_entries": len(db_entries),
        "preserved_index_entries": len(merged) - len(db_entries),
        "updated_session_index": updated_session_index,
    }


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
    db_backup, database_backups = make_backup(paths)
    db_result = update_database_threads(paths, profile)
    timestamp_result = repair_database_thread_timestamps(paths)
    session_result = update_session_files(paths, profile)
    index_result = merge_session_index(paths)
    global_state_result = sync_global_state(paths)
    return {
        "ok": True,
        "skipped": False,
        "current_provider": profile.provider,
        "current_model": profile.model,
        "backup_path": str(db_backup),
        "database_backup_paths": [str(path) for path in database_backups],
        **db_result,
        **timestamp_result,
        **session_result,
        **index_result,
        **global_state_result,
    }


def sync_history_visibility_to_current_profile(paths: HistoryPaths) -> dict[str, object]:
    missing = environment_missing_reason(paths)
    if missing:
        raise RuntimeError(missing)
    profile = read_current_profile(paths)
    try:
        with ProviderSyncLock(provider_sync_lock_path(paths)):
            db_backup, database_backups = make_backup(paths, "provider-switch")
            changes = collect_provider_sync_session_changes(paths, profile)
            written: list[ProviderSyncSessionChange] = []
            skipped_session_files: list[str] = []
            try:
                written, skipped_session_files = write_provider_sync_session_changes(changes)
                db_result = update_provider_visibility_database_threads(paths, profile, changes)
            except Exception as exc:
                restore_provider_sync_session_changes(written)
                return {
                    "ok": True,
                    "skipped": True,
                    "visibility_only": True,
                    "current_provider": profile.provider,
                    "current_model": profile.model,
                    "backup_path": str(db_backup),
                    "database_backup_paths": [str(path) for path in database_backups],
                    "reason": f"Provider sync skipped: {exc}",
                    "updated_session_files": 0,
                    "skipped_session_files": skipped_session_files,
                }
            result: dict[str, object] = {
                "ok": True,
                "skipped": False,
                "visibility_only": True,
                "current_provider": profile.provider,
                "current_model": profile.model,
                "backup_path": str(db_backup),
                "database_backup_paths": [str(path) for path in database_backups],
                "updated_session_files": len(written),
                "skipped_session_files": skipped_session_files,
                **db_result,
            }
            if any(change.encrypted_provider_warning for change in changes):
                result["encrypted_content_warning"] = (
                    "检测到包含 encrypted_content 的旧供应商会话。已修复可见性字段，"
                    "但继续旧会话时仍可能需要切回原供应商或新开会话。"
                )
            return result
    except RuntimeError as exc:
        if "provider sync lock exists" in str(exc):
            return {
                "ok": True,
                "skipped": True,
                "visibility_only": True,
                "current_provider": profile.provider,
                "current_model": profile.model,
                "reason": str(exc),
            }
        raise


def sync_history_visibility_if_ready(paths: HistoryPaths) -> dict[str, object]:
    missing = environment_missing_reason(paths)
    if missing:
        return {"ok": True, "skipped": True, "reason": missing}
    current_status = status(paths)
    mismatched_provider = int(current_status.get("mismatched_provider_threads") or 0)
    mismatched_sessions = int(current_status.get("mismatched_session_provider_files") or 0)
    if mismatched_provider == 0 and mismatched_sessions == 0:
        return {
            **current_status,
            "skipped": True,
            "visibility_only": True,
            "reason": "history already matches current provider",
        }
    return {**current_status, **sync_history_visibility_to_current_profile(paths)}


def sync_history_if_ready(paths: HistoryPaths) -> dict[str, object]:
    missing = environment_missing_reason(paths)
    if missing:
        return {"ok": True, "skipped": True, "reason": missing}
    current_status = status(paths)
    mismatched_provider = int(current_status.get("mismatched_provider_threads") or 0)
    mismatched_model = int(current_status.get("mismatched_model_threads") or 0)
    mismatched_sessions = int(current_status.get("mismatched_session_files") or 0)
    if mismatched_provider == 0 and mismatched_model == 0 and mismatched_sessions == 0:
        return {
            **current_status,
            "skipped": True,
            "reason": "history already matches current provider/model",
        }
    return {**current_status, **sync_history_to_current_profile(paths)}


def status(paths: HistoryPaths) -> dict[str, object]:
    missing = environment_missing_reason(paths)
    if missing:
        return {"ok": True, "ready": False, "reason": missing}
    profile = read_current_profile(paths)
    thread_records: dict[str, list[tuple[str | None, str | None]]] = {}
    skipped_database_paths: list[str] = []
    any_model_column = False
    for db_path in database_paths(paths):
        try:
            with connect_db(db_path, readonly=True) as conn:
                if not table_exists(conn, "threads"):
                    skipped_database_paths.append(f"{db_path}: missing threads table")
                    continue
                columns = table_columns(conn, "threads")
                if "id" not in columns:
                    skipped_database_paths.append(f"{db_path}: missing id column")
                    continue
                any_model_column = any_model_column or "model" in columns
                provider_expr = "model_provider" if "model_provider" in columns else "NULL AS model_provider"
                model_expr = "model" if "model" in columns else "NULL AS model"
                rows = conn.execute(f"SELECT id, {provider_expr}, {model_expr} FROM threads").fetchall()
        except sqlite3.Error as exc:
            skipped_database_paths.append(f"{db_path}: {exc}")
            continue
        for row in rows:
            thread_id = str(row["id"])
            provider = str(row["model_provider"] or "") or None
            model = str(row["model"] or "") if row["model"] else None
            thread_records.setdefault(thread_id, []).append((provider, model))
    thread_ids = set(thread_records)
    total = len(thread_ids)
    mismatched_provider = sum(
        1 for records in thread_records.values() if any(provider != profile.provider for provider, _ in records)
    )
    mismatched_model = None
    if profile.model and any_model_column:
        mismatched_model = sum(
            1 for records in thread_records.values() if any(model != profile.model for _, model in records)
        )
    session_file_count = len(iter_session_files(paths))
    session_status = session_profile_status(paths, profile, thread_ids)
    payload: dict[str, object] = {
        "ok": True,
        "ready": True,
        "current_provider": profile.provider,
        "current_model": profile.model,
        "total_threads": total,
        "mismatched_provider_threads": mismatched_provider,
        "mismatched_model_threads": mismatched_model,
        "database_file_count": len(database_paths(paths)),
        "database_paths": [str(path) for path in database_paths(paths)],
        "skipped_database_paths": skipped_database_paths,
        "session_file_count": session_file_count,
        "session_index_count": len(read_session_index_entries(paths)),
        **session_status,
    }
    if total == 0 and skipped_database_paths:
        payload["skipped_database_status"] = skipped_database_paths
    return payload
