from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from codex_session_delete import history_sync


def write_config(home: Path, provider: str = "current_provider", model: str = "gpt-current") -> None:
    home.mkdir(parents=True, exist_ok=True)
    (home / "config.toml").write_text(
        f'model_provider = "{provider}"\nmodel = "{model}"\n',
        encoding="utf-8",
    )


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


def test_sync_history_skips_when_codex_state_is_missing(tmp_path):
    paths = history_sync.resolve_paths(tmp_path / ".codex")

    result = history_sync.sync_history_if_ready(paths)

    assert result["ok"] is True
    assert result["skipped"] is True
    assert "missing" in result["reason"]
