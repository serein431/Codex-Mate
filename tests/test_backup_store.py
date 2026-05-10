import json

from codex_session_delete.backup_store import BackupStore


def test_backup_store_writes_and_reads_backup(tmp_path):
    store = BackupStore(tmp_path)
    token = store.write_backup(
        session_id="s1",
        source_db="C:/state/codex.sqlite",
        tables={"sessions": [{"id": "s1", "title": "Hello"}]},
    )

    backup = store.read_backup(token)

    assert backup["session_id"] == "s1"
    assert backup["source_db"] == "C:/state/codex.sqlite"
    assert backup["tables"]["sessions"][0]["title"] == "Hello"


def test_backup_store_rejects_unknown_token(tmp_path):
    store = BackupStore(tmp_path)

    try:
        store.read_backup("missing")
    except FileNotFoundError as exc:
        assert "missing" in str(exc)


def test_write_backup_recreates_missing_backup_directory(tmp_path):
    backup_dir = tmp_path / "backups"
    store = BackupStore(backup_dir)
    backup_dir.rmdir()

    token = store.write_backup("s1", "db.sqlite", {"sessions": []})

    assert store.path_for(token).exists()
