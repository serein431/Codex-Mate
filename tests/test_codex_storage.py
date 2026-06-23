import sqlite3

from codex_mate import codex_storage


def create_thread_db(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE threads (id TEXT PRIMARY KEY)")


def test_discovers_sqlite_thread_dbs_before_legacy_db(tmp_path):
    home = tmp_path / ".codex"
    new_db = home / "sqlite" / "state_5.sqlite"
    legacy_db = home / "state_5.sqlite"
    create_thread_db(new_db)
    create_thread_db(legacy_db)
    (home / "sqlite" / "state_5.sqlite-wal").write_text("not a db", encoding="utf-8")

    paths = codex_storage.discover_thread_db_paths(home)

    assert paths == [new_db, legacy_db]
    assert codex_storage.primary_thread_db_path(home) == new_db


def test_codex_home_for_db_path_handles_sqlite_subdirectory(tmp_path):
    home = tmp_path / ".codex"

    assert codex_storage.codex_home_for_db_path(home / "sqlite" / "state_5.sqlite") == home
    assert codex_storage.codex_home_for_db_path(home / "state_5.sqlite") == home


def test_rollout_dirs_include_sessions_and_archived_sessions(tmp_path):
    home = tmp_path / ".codex"
    sessions = home / "sessions"
    archived = home / "archived_sessions"
    sessions.mkdir(parents=True)
    archived.mkdir()

    assert codex_storage.rollout_dirs(home) == [sessions, archived]
