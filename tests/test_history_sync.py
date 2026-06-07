from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from codex_mate import history_sync


def write_config(home: Path, provider: str = "current_provider", model: str = "gpt-current") -> None:
    home.mkdir(parents=True, exist_ok=True)
    (home / "config.toml").write_text(
        f'model_provider = "{provider}"\nmodel = "{model}"\n',
        encoding="utf-8",
    )


def write_openai_default_config(home: Path, model: str = "gpt-current") -> None:
    home.mkdir(parents=True, exist_ok=True)
    (home / "config.toml").write_text(f'model = "{model}"\n', encoding="utf-8")


def create_threads_db(home: Path) -> None:
    conn = sqlite3.connect(home / "state_5.sqlite")
    try:
        conn.execute(
            """
            CREATE TABLE threads (
                id TEXT PRIMARY KEY,
                title TEXT,
                updated_at INTEGER,
                archived INTEGER DEFAULT 0,
                model_provider TEXT,
                model TEXT
            )
            """
        )
        conn.executemany(
            "INSERT INTO threads (id, title, updated_at, archived, model_provider, model) VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("old-thread", "Old Thread", 100, 0, "old_provider", "gpt-old"),
                ("already-current", "Current Thread", 200, 0, "current_provider", "gpt-current"),
                ("archived-thread", "Archived", 300, 1, "old_provider", "gpt-old"),
            ],
        )
        conn.commit()
    finally:
        conn.close()


def create_current_threads_db(home: Path) -> None:
    conn = sqlite3.connect(home / "state_5.sqlite")
    try:
        conn.execute(
            """
            CREATE TABLE threads (
                id TEXT PRIMARY KEY,
                title TEXT,
                updated_at INTEGER,
                archived INTEGER DEFAULT 0,
                model_provider TEXT,
                model TEXT
            )
            """
        )
        conn.executemany(
            "INSERT INTO threads (id, title, updated_at, archived, model_provider, model) VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("current-thread", "Current Thread", 100, 0, "current_provider", "gpt-current"),
                ("current-thread-2", "Current Thread 2", 200, 0, "current_provider", "gpt-current"),
            ],
        )
        conn.commit()
    finally:
        conn.close()


def create_threads_db_with_cwd(home: Path) -> None:
    conn = sqlite3.connect(home / "state_5.sqlite")
    try:
        conn.execute(
            """
            CREATE TABLE threads (
                id TEXT PRIMARY KEY,
                title TEXT,
                updated_at INTEGER,
                updated_at_ms INTEGER,
                archived INTEGER DEFAULT 0,
                model_provider TEXT,
                model TEXT,
                cwd TEXT NOT NULL DEFAULT ''
            )
            """
        )
        conn.executemany(
            "INSERT INTO threads (id, title, updated_at, updated_at_ms, archived, model_provider, model, cwd) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("project-thread", "Project Thread", 100, 100000, 0, "old_provider", "gpt-old", "/work/project"),
                ("project-thread-2", "Project Thread 2", 200, 200000, 0, "old_provider", "gpt-old", "/work/project"),
                ("project-thread-other", "Other Project", 300, 300000, 0, "old_provider", "gpt-old", "/work/other"),
                ("empty-cwd-thread", "No Project", 400, 400000, 0, "old_provider", "gpt-old", ""),
                ("archived-thread", "Archived", 500, 500000, 1, "old_provider", "gpt-old", "/work/project"),
            ],
        )
        conn.commit()
    finally:
        conn.close()


def write_session_file(home: Path, thread_id: str, provider: str, model: str) -> Path:
    session_dir = home / "sessions" / "2026" / "01"
    session_dir.mkdir(parents=True, exist_ok=True)
    path = session_dir / f"rollout-2026-01-01T00-00-00-{thread_id}.jsonl"
    first = {
        "type": "session_meta",
        "payload": {
            "id": thread_id,
            "model_provider": provider,
            "model": model,
        },
    }
    path.write_text(json.dumps(first) + "\n{\"type\":\"event_msg\",\"payload\":{}}\n", encoding="utf-8")
    return path


def test_sync_history_rehomes_database_sessions_and_index(tmp_path):
    home = tmp_path / ".codex"
    write_config(home)
    create_threads_db(home)
    session_path = write_session_file(home, "old-thread", "old_provider", "gpt-old")
    (home / "session_index.jsonl").write_text(
        json.dumps({"id": "already-current", "thread_name": "Current Thread", "updated_at": "1970-01-01T00:00:00Z"}) + "\n",
        encoding="utf-8",
    )
    paths = history_sync.resolve_paths(home)

    result = history_sync.sync_history_to_current_profile(paths)

    assert result["updated_database_rows"] == 2
    assert result["updated_session_files"] == 1
    assert result["rewritten_index_entries"] == 2
    assert Path(result["backup_path"]).exists()
    assert Path(result["backup_path"] + ".session_index.jsonl").exists()
    assert Path(result["backup_path"] + ".session_meta.json").exists()

    with sqlite3.connect(home / "state_5.sqlite") as conn:
        rows = conn.execute(
            "SELECT model_provider, model, COUNT(*) FROM threads GROUP BY model_provider, model"
        ).fetchall()
    assert rows == [("current_provider", "gpt-current", 3)]

    first_line = session_path.read_text(encoding="utf-8").splitlines()[0]
    payload = json.loads(first_line)["payload"]
    assert payload["model_provider"] == "current_provider"
    assert payload["model"] == "gpt-current"

    index_entries = [json.loads(line) for line in (home / "session_index.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [entry["id"] for entry in index_entries] == ["old-thread", "already-current"]
    assert index_entries[0]["thread_name"] == "Old Thread"


def test_sync_history_defaults_to_openai_when_model_provider_is_missing(tmp_path):
    home = tmp_path / ".codex"
    write_openai_default_config(home, model="gpt-current")
    create_threads_db(home)
    session_path = write_session_file(home, "old-thread", "old_provider", "gpt-old")
    paths = history_sync.resolve_paths(home)

    result = history_sync.sync_history_to_current_profile(paths)

    assert result["current_provider"] == "openai"
    assert result["updated_database_rows"] == 3
    with sqlite3.connect(home / "state_5.sqlite") as conn:
        rows = conn.execute(
            "SELECT model_provider, model, COUNT(*) FROM threads GROUP BY model_provider, model"
        ).fetchall()
    assert rows == [("openai", "gpt-current", 3)]

    first_line = session_path.read_text(encoding="utf-8").splitlines()[0]
    payload = json.loads(first_line)["payload"]
    assert payload["model_provider"] == "openai"
    assert payload["model"] == "gpt-current"


def test_sync_history_preserves_existing_index_entries_with_session_file(tmp_path):
    home = tmp_path / ".codex"
    write_config(home)
    create_threads_db(home)
    write_session_file(home, "file-only", "current_provider", "gpt-current")
    (home / "session_index.jsonl").write_text(
        json.dumps({"id": "file-only", "thread_name": "File Only", "updated_at": "2026-01-01T00:00:00Z"}) + "\n",
        encoding="utf-8",
    )
    paths = history_sync.resolve_paths(home)

    result = history_sync.sync_history_to_current_profile(paths)

    assert result["rewritten_index_entries"] == 3
    assert result["preserved_index_entries"] == 1
    index_entries = [json.loads(line) for line in (home / "session_index.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [entry["id"] for entry in index_entries] == ["old-thread", "already-current", "file-only"]


def test_merge_session_index_preserves_existing_updated_at_and_avoids_rewriting_when_unchanged(tmp_path):
    home = tmp_path / ".codex"
    write_config(home)
    conn = sqlite3.connect(home / "state_5.sqlite")
    try:
        conn.execute(
            """
            CREATE TABLE threads (
                id TEXT PRIMARY KEY,
                title TEXT,
                updated_at INTEGER,
                updated_at_ms INTEGER,
                archived INTEGER DEFAULT 0,
                model_provider TEXT,
                model TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO threads (id, title, updated_at, updated_at_ms, archived, model_provider, model) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("thread-ms", "Fresh Title", 100, 1500, 0, "current_provider", "gpt-current"),
        )
        conn.commit()
    finally:
        conn.close()
    paths = history_sync.resolve_paths(home)
    (home / "session_index.jsonl").write_text(
        json.dumps({"id": "thread-ms", "thread_name": "Stale Title", "updated_at": "1970-01-01T00:00:00Z"}) + "\n",
        encoding="utf-8",
    )

    first = history_sync.merge_session_index(paths)
    content = (home / "session_index.jsonl").read_text(encoding="utf-8")
    second = history_sync.merge_session_index(paths)

    assert first["updated_session_index"] is True
    assert json.loads(content)["thread_name"] == "Stale Title"
    assert json.loads(content)["updated_at"] == "1970-01-01T00:00:00Z"
    assert second["updated_session_index"] is False
    assert (home / "session_index.jsonl").read_text(encoding="utf-8") == content


def test_merge_session_index_preserves_existing_thread_name_when_database_title_is_first_message(tmp_path):
    home = tmp_path / ".codex"
    write_config(home)
    conn = sqlite3.connect(home / "state_5.sqlite")
    try:
        conn.execute(
            """
            CREATE TABLE threads (
                id TEXT PRIMARY KEY,
                title TEXT,
                updated_at_ms INTEGER,
                archived INTEGER DEFAULT 0,
                model_provider TEXT,
                model TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO threads (id, title, updated_at_ms, archived, model_provider, model) VALUES (?, ?, ?, ?, ?, ?)",
            ("thread-title", "这是用户说的第一句话，不应该覆盖生成标题", 2000, 0, "current_provider", "gpt-current"),
        )
        conn.commit()
    finally:
        conn.close()
    (home / "session_index.jsonl").write_text(
        json.dumps({"id": "thread-title", "thread_name": "生成后的会话标题", "updated_at": "1970-01-01T00:00:00Z"}) + "\n",
        encoding="utf-8",
    )
    paths = history_sync.resolve_paths(home)

    result = history_sync.merge_session_index(paths)

    entry = json.loads((home / "session_index.jsonl").read_text(encoding="utf-8"))
    assert result["updated_session_index"] is True
    assert entry["thread_name"] == "生成后的会话标题"
    assert entry["updated_at"] == "1970-01-01T00:00:00Z"


def test_merge_session_index_prefers_latest_rollout_timestamp(tmp_path):
    home = tmp_path / ".codex"
    write_config(home)
    session_path = write_session_file(home, "thread-rollout", "current_provider", "gpt-current")
    session_path.write_text(
        json.dumps(
            {
                "type": "session_meta",
                "timestamp": "2026-01-01T00:00:00.000Z",
                "payload": {"id": "thread-rollout", "model_provider": "current_provider", "model": "gpt-current"},
            }
        )
        + "\n"
        + json.dumps({"type": "event_msg", "timestamp": "2026-01-01T00:05:42.987Z", "payload": {}})
        + "\n",
        encoding="utf-8",
    )
    conn = sqlite3.connect(home / "state_5.sqlite")
    try:
        conn.execute(
            """
            CREATE TABLE threads (
                id TEXT PRIMARY KEY,
                title TEXT,
                rollout_path TEXT,
                updated_at INTEGER,
                updated_at_ms INTEGER,
                archived INTEGER DEFAULT 0,
                model_provider TEXT,
                model TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO threads (id, title, rollout_path, updated_at, updated_at_ms, archived, model_provider, model) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("thread-rollout", "Rollout Time", str(session_path), 1767225600, 1767225600000, 0, "current_provider", "gpt-current"),
        )
        conn.commit()
    finally:
        conn.close()
    paths = history_sync.resolve_paths(home)

    result = history_sync.merge_session_index(paths)

    assert result["updated_session_index"] is True
    entry = json.loads((home / "session_index.jsonl").read_text(encoding="utf-8"))
    assert entry["updated_at"] == "2026-01-01T00:05:42Z"


def test_sync_history_prunes_orphan_index_entries_without_database_or_session_file(tmp_path):
    home = tmp_path / ".codex"
    write_config(home)
    create_threads_db(home)
    (home / "session_index.jsonl").write_text(
        json.dumps({"id": "orphan", "thread_name": "Orphan", "updated_at": "2026-01-01T00:00:00Z"}) + "\n",
        encoding="utf-8",
    )
    paths = history_sync.resolve_paths(home)

    result = history_sync.sync_history_to_current_profile(paths)

    assert result["rewritten_index_entries"] == 2
    assert result["preserved_index_entries"] == 0
    index_entries = [json.loads(line) for line in (home / "session_index.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [entry["id"] for entry in index_entries] == ["old-thread", "already-current"]


def test_sync_history_does_not_clear_index_when_threads_table_is_missing(tmp_path):
    home = tmp_path / ".codex"
    write_config(home)
    sqlite3.connect(home / "state_5.sqlite").close()
    (home / "session_index.jsonl").write_text(
        json.dumps({"id": "existing-thread", "thread_name": "Existing Thread", "updated_at": "2026-01-01T00:00:00Z"}) + "\n",
        encoding="utf-8",
    )
    paths = history_sync.resolve_paths(home)

    result = history_sync.sync_history_to_current_profile(paths)

    assert result["updated_database_rows"] == 0
    assert result["rewritten_index_entries"] == 1
    index_entries = [json.loads(line) for line in (home / "session_index.jsonl").read_text(encoding="utf-8").splitlines()]
    assert index_entries == [{"id": "existing-thread", "thread_name": "Existing Thread", "updated_at": "2026-01-01T00:00:00Z"}]


def test_sync_history_skips_locked_session_files_without_aborting(tmp_path, monkeypatch):
    home = tmp_path / ".codex"
    write_config(home)
    create_threads_db(home)
    locked_path = write_session_file(home, "old-thread", "old_provider", "gpt-old")
    updated_path = write_session_file(home, "already-current", "old_provider", "gpt-old")
    original_atomic_write_text = history_sync.atomic_write_text

    def fail_locked_file(path: Path, text: str) -> None:
        if path == locked_path:
            raise PermissionError("Access is denied")
        original_atomic_write_text(path, text)

    monkeypatch.setattr(history_sync, "atomic_write_text", fail_locked_file)

    result = history_sync.sync_history_to_current_profile(history_sync.resolve_paths(home))

    assert result["updated_session_files"] == 1
    assert len(result["skipped_session_files"]) == 1
    assert "Access is denied" in result["skipped_session_files"][0]
    payload = json.loads(updated_path.read_text(encoding="utf-8").splitlines()[0])["payload"]
    assert payload["model_provider"] == "current_provider"


def test_sync_history_updates_session_meta_beyond_first_line(tmp_path):
    home = tmp_path / ".codex"
    write_config(home)
    create_threads_db(home)
    session_path = write_session_file(home, "old-thread", "old_provider", "gpt-old")
    session_path.write_text(
        json.dumps({"timestamp": "2026-01-01T00:00:00.000Z", "type": "event_msg", "payload": {"type": "started"}})
        + "\n"
        + json.dumps(
            {
                "timestamp": "2026-01-01T00:00:01.000Z",
                "type": "session_meta",
                "payload": {"id": "old-thread", "model_provider": "old_provider", "model": "gpt-old"},
            }
        )
        + "\n"
        + json.dumps({"timestamp": "2026-01-01T00:00:02.000Z", "type": "event_msg", "payload": {"type": "token_count"}})
        + "\n",
        encoding="utf-8",
    )

    result = history_sync.sync_history_to_current_profile(history_sync.resolve_paths(home))

    assert result["updated_session_files"] == 1
    lines = session_path.read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[0])["type"] == "event_msg"
    payload = json.loads(lines[1])["payload"]
    assert payload["model_provider"] == "current_provider"
    assert payload["model"] == "gpt-current"
    assert json.loads(lines[2])["type"] == "event_msg"


def test_sync_history_to_current_profile_preserves_session_meta_timestamp_when_repairing_sidecars(tmp_path):
    home = tmp_path / ".codex"
    write_config(home)
    create_current_threads_db(home)
    session_path = write_session_file(home, "current-thread", "current_provider", "gpt-current")
    session_path.write_text(
        json.dumps(
            {
                "timestamp": "2026-01-01T00:00:00.000Z",
                "type": "session_meta",
                "payload": {
                    "id": "current-thread",
                    "timestamp": "2026-01-01T00:00:00.000Z",
                    "model_provider": "current_provider",
                    "model": "gpt-current",
                },
            }
        )
        + "\n"
        + json.dumps({"timestamp": "2026-01-01T00:09:08.765Z", "type": "event_msg", "payload": {"type": "token_count"}})
        + "\n",
        encoding="utf-8",
    )

    result = history_sync.sync_history_to_current_profile(history_sync.resolve_paths(home))

    assert result["updated_session_files"] == 0
    first_line = json.loads(session_path.read_text(encoding="utf-8").splitlines()[0])
    assert first_line["timestamp"] == "2026-01-01T00:00:00.000Z"
    assert first_line["payload"]["timestamp"] == "2026-01-01T00:00:00.000Z"


def test_sync_history_skips_when_codex_state_is_missing(tmp_path):
    paths = history_sync.resolve_paths(tmp_path / ".codex")

    result = history_sync.sync_history_if_ready(paths)

    assert result["ok"] is True
    assert result["skipped"] is True
    assert "missing" in result["reason"]


def test_sync_history_if_ready_skips_when_profile_already_matches(tmp_path):
    home = tmp_path / ".codex"
    write_config(home)
    create_current_threads_db(home)
    paths = history_sync.resolve_paths(home)

    result = history_sync.sync_history_if_ready(paths)

    assert result["ok"] is True
    assert result["skipped"] is True
    assert result["mismatched_provider_threads"] == 0
    assert result["mismatched_model_threads"] == 0
    assert "backup_path" not in result
    assert not (home / "codex_mate_history_backups").exists()


def test_sync_history_if_ready_skips_stale_index_when_profile_matches(tmp_path):
    home = tmp_path / ".codex"
    write_config(home)
    create_current_threads_db(home)
    (home / "session_index.jsonl").write_text(
        json.dumps({"id": "current-thread", "thread_name": "Existing Title", "updated_at": "1970-01-01T00:00:00Z"}) + "\n",
        encoding="utf-8",
    )
    paths = history_sync.resolve_paths(home)

    result = history_sync.sync_history_if_ready(paths)

    assert result["ok"] is True
    assert result["skipped"] is True
    assert result["mismatched_provider_threads"] == 0
    assert result["mismatched_model_threads"] == 0
    assert "sidecar_repaired" not in result
    assert "backup_path" not in result
    assert not (home / "codex_mate_history_backups").exists()
    index_entries = [json.loads(line) for line in (home / "session_index.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [entry["id"] for entry in index_entries] == ["current-thread"]
    assert index_entries[0]["thread_name"] == "Existing Title"
    assert index_entries[0]["updated_at"] == "1970-01-01T00:00:00Z"


def test_sync_history_if_ready_skips_stale_database_timestamp_when_profile_matches(tmp_path):
    home = tmp_path / ".codex"
    write_config(home)
    session_path = write_session_file(home, "current-thread", "current_provider", "gpt-current")
    session_path.write_text(
        json.dumps(
            {
                "timestamp": "2026-01-01T00:00:00.000Z",
                "type": "session_meta",
                "payload": {"id": "current-thread", "model_provider": "current_provider", "model": "gpt-current"},
            }
        )
        + "\n"
        + json.dumps({"timestamp": "2026-01-01T00:07:06.321Z", "type": "event_msg", "payload": {"type": "token_count"}})
        + "\n",
        encoding="utf-8",
    )
    conn = sqlite3.connect(home / "state_5.sqlite")
    try:
        conn.execute(
            """
            CREATE TABLE threads (
                id TEXT PRIMARY KEY,
                title TEXT,
                rollout_path TEXT,
                updated_at INTEGER,
                updated_at_ms INTEGER,
                archived INTEGER DEFAULT 0,
                model_provider TEXT,
                model TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO threads (id, title, rollout_path, updated_at, updated_at_ms, archived, model_provider, model) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("current-thread", "Current Thread", str(session_path), 1767225600, 1767225600000, 0, "current_provider", "gpt-current"),
        )
        conn.commit()
    finally:
        conn.close()

    result = history_sync.sync_history_if_ready(history_sync.resolve_paths(home))

    assert result["ok"] is True
    assert result["skipped"] is True
    assert result["mismatched_provider_threads"] == 0
    assert result["mismatched_model_threads"] == 0
    assert "updated_database_timestamps" not in result
    assert "updated_session_files" not in result
    with sqlite3.connect(home / "state_5.sqlite") as conn:
        row = conn.execute("SELECT updated_at, updated_at_ms FROM threads WHERE id = ?", ("current-thread",)).fetchone()
    assert row == (1767225600, 1767225600000)
    assert not (home / "session_index.jsonl").exists()


def test_sync_history_if_ready_syncs_when_profile_mismatches(tmp_path):
    home = tmp_path / ".codex"
    write_config(home)
    create_threads_db(home)
    paths = history_sync.resolve_paths(home)

    result = history_sync.sync_history_if_ready(paths)

    assert result["ok"] is True
    assert result["skipped"] is False
    assert result["updated_database_rows"] == 2
    assert Path(result["backup_path"]).exists()


def test_sync_history_visibility_if_ready_skips_heavy_sidebar_rewrites(tmp_path):
    home = tmp_path / ".codex"
    write_config(home)
    create_threads_db(home)
    session_path = write_session_file(home, "old-thread", "old_provider", "gpt-old")
    session_index = json.dumps({"id": "old-thread", "thread_name": "Old Thread", "updated_at": "1970-01-01T00:00:00Z"}) + "\n"
    global_state = '{"project-order":["/keep"],"thread-workspace-root-hints":{"old-thread":"/keep"}}\n'
    (home / "session_index.jsonl").write_text(session_index, encoding="utf-8")
    (home / ".codex-global-state.json").write_text(global_state, encoding="utf-8")

    result = history_sync.sync_history_visibility_if_ready(history_sync.resolve_paths(home))

    assert result["ok"] is True
    assert result["skipped"] is False
    assert result["visibility_only"] is True
    assert result["updated_database_rows"] == 2
    assert result["updated_session_files"] == 1
    assert "updated_database_timestamps" not in result
    assert "rewritten_index_entries" not in result
    assert "updated_global_state" not in result
    assert Path(result["backup_path"]).exists()
    assert Path(result["backup_path"] + ".session_index.jsonl").exists()
    assert (home / "session_index.jsonl").read_text(encoding="utf-8") == session_index
    assert (home / ".codex-global-state.json").read_text(encoding="utf-8") == global_state

    with sqlite3.connect(home / "state_5.sqlite") as conn:
        rows = conn.execute("SELECT model_provider, model, COUNT(*) FROM threads GROUP BY model_provider, model").fetchall()
    assert rows == [("current_provider", "gpt-current", 3)]
    payload = json.loads(session_path.read_text(encoding="utf-8").splitlines()[0])["payload"]
    assert payload["model_provider"] == "current_provider"
    assert payload["model"] == "gpt-current"


def test_sync_history_repairs_desktop_global_state_sidebar_indexes(tmp_path):
    home = tmp_path / ".codex"
    write_config(home)
    create_threads_db_with_cwd(home)
    (home / ".codex-global-state.json").write_text(
        json.dumps(
            {
                "projectless-thread-ids": ["existing-thread", "project-thread"],
                "thread-workspace-root-hints": {"existing-thread": "/existing"},
                "project-order": ["/existing"],
                "electron-saved-workspace-roots": ["/existing"],
            }
        ),
        encoding="utf-8",
    )

    result = history_sync.sync_history_to_current_profile(history_sync.resolve_paths(home))

    assert result["updated_global_state"] is True
    assert result["global_state_thread_hints_added"] == 3
    assert result["global_state_project_roots_added"] == 0
    assert result["global_state_saved_roots_added"] == 0
    assert result["global_state_projectless_threads_added"] == 1
    assert result["global_state_projectless_threads_removed"] == 1
    assert Path(result["backup_path"] + ".codex-global-state.json").exists()

    state = json.loads((home / ".codex-global-state.json").read_text(encoding="utf-8"))
    assert state["thread-workspace-root-hints"]["project-thread"] == "/work/project"
    assert state["thread-workspace-root-hints"]["project-thread-2"] == "/work/project"
    assert state["thread-workspace-root-hints"]["project-thread-other"] == "/work/other"
    assert state["project-order"] == ["/existing"]
    assert state["electron-saved-workspace-roots"] == ["/existing"]
    assert "project-thread" not in state["projectless-thread-ids"]
    assert "project-thread-2" not in state["projectless-thread-ids"]
    assert "project-thread-other" not in state["projectless-thread-ids"]
    assert "empty-cwd-thread" in state["projectless-thread-ids"]
    assert "archived-thread" not in state["projectless-thread-ids"]


def test_sync_global_state_is_idempotent(tmp_path):
    home = tmp_path / ".codex"
    write_config(home)
    create_threads_db_with_cwd(home)
    paths = history_sync.resolve_paths(home)

    first = history_sync.sync_global_state(paths)
    second = history_sync.sync_global_state(paths)

    assert first["updated_global_state"] is True
    assert second["updated_global_state"] is False
    assert second["global_state_thread_hints_added"] == 0
    assert second["global_state_project_roots_added"] == 0
    assert second["global_state_projectless_threads_added"] == 0
    assert second["global_state_projectless_threads_removed"] == 0
