import json
import sqlite3

from codex_mate.backup_store import BackupStore
from codex_mate.models import DeleteStatus, SessionRef
from codex_mate.storage_adapter import SQLiteStorageAdapter


def create_supported_db(path):
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY, title TEXT NOT NULL)")
        db.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT NOT NULL, body TEXT NOT NULL)")
        db.execute("INSERT INTO sessions (id, title) VALUES ('s1', 'First')")
        db.execute("INSERT INTO messages (session_id, body) VALUES ('s1', 'hello')")


def create_codex_thread_db(path, rollout_path):
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE threads (id TEXT PRIMARY KEY, rollout_path TEXT, title TEXT, archived INTEGER, archived_at INTEGER)")
        db.execute("CREATE TABLE thread_dynamic_tools (thread_id TEXT NOT NULL, tool_name TEXT NOT NULL)")
        db.execute("CREATE TABLE thread_goals (thread_id TEXT NOT NULL, goal TEXT NOT NULL)")
        db.execute("CREATE TABLE thread_spawn_edges (parent_thread_id TEXT NOT NULL, child_thread_id TEXT NOT NULL, status TEXT NOT NULL)")
        db.execute("CREATE TABLE stage1_outputs (thread_id TEXT NOT NULL, output TEXT NOT NULL)")
        db.execute("CREATE TABLE agent_job_items (id TEXT PRIMARY KEY, assigned_thread_id TEXT)")
        db.execute("INSERT INTO threads (id, rollout_path, title, archived, archived_at) VALUES ('t1', ?, 'Codex Thread', 0, NULL)", (str(rollout_path),))
        db.execute("INSERT INTO thread_dynamic_tools (thread_id, tool_name) VALUES ('t1', 'Read')")
        db.execute("INSERT INTO thread_goals (thread_id, goal) VALUES ('t1', 'delete me')")
        db.execute("INSERT INTO thread_spawn_edges (parent_thread_id, child_thread_id, status) VALUES ('t1', 'child', 'running')")
        db.execute("INSERT INTO thread_spawn_edges (parent_thread_id, child_thread_id, status) VALUES ('parent', 't1', 'done')")
        db.execute("INSERT INTO stage1_outputs (thread_id, output) VALUES ('t1', 'cached')")
        db.execute("INSERT INTO agent_job_items (id, assigned_thread_id) VALUES ('job1', 't1')")


def test_delete_local_session_creates_backup_and_removes_rows(tmp_path):
    db_path = tmp_path / "codex.sqlite"
    create_supported_db(db_path)
    adapter = SQLiteStorageAdapter(db_path, BackupStore(tmp_path / "backups"))

    result = adapter.delete_local(SessionRef(session_id="s1", title="First"))

    assert result.status == DeleteStatus.LOCAL_DELETED
    assert result.undo_token is not None
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 0


def test_undo_restores_deleted_rows(tmp_path):
    db_path = tmp_path / "codex.sqlite"
    create_supported_db(db_path)
    adapter = SQLiteStorageAdapter(db_path, BackupStore(tmp_path / "backups"))
    deleted = adapter.delete_local(SessionRef(session_id="s1", title="First"))

    restored = adapter.undo(deleted.undo_token or "")

    assert restored.status == DeleteStatus.UNDONE
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT title FROM sessions WHERE id = 's1'").fetchone()[0] == "First"
        assert db.execute("SELECT body FROM messages WHERE session_id = 's1'").fetchone()[0] == "hello"




def test_delete_codex_thread_schema_creates_backup_and_removes_thread_rows(tmp_path):
    db_path = tmp_path / "state_5.sqlite"
    rollout_path = tmp_path / "rollout.jsonl"
    rollout_path.write_text('{"type":"message"}\n', encoding="utf-8")
    create_codex_thread_db(db_path, rollout_path)
    adapter = SQLiteStorageAdapter(db_path, BackupStore(tmp_path / "backups"))

    result = adapter.delete_local(SessionRef(session_id="t1", title="Codex Thread"))

    assert result.status == DeleteStatus.LOCAL_DELETED
    assert result.undo_token is not None
    assert not rollout_path.exists()
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT COUNT(*) FROM threads WHERE id = 't1'").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM thread_dynamic_tools WHERE thread_id = 't1'").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM thread_goals WHERE thread_id = 't1'").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM thread_spawn_edges WHERE parent_thread_id = 't1' OR child_thread_id = 't1'").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM stage1_outputs WHERE thread_id = 't1'").fetchone()[0] == 0
        assert db.execute("SELECT assigned_thread_id FROM agent_job_items WHERE id = 'job1'").fetchone()[0] is None


def test_delete_codex_thread_schema_removes_codex_sidecar_indexes(tmp_path):
    db_path = tmp_path / "state_5.sqlite"
    rollout_path = tmp_path / "rollout.jsonl"
    rollout_path.write_text('{"type":"message"}\n', encoding="utf-8")
    create_codex_thread_db(db_path, rollout_path)
    (tmp_path / "session_index.jsonl").write_text(
        '{"id":"keep","thread_name":"Keep","updated_at":"2026-05-01T00:00:00Z"}\n'
        '{"id":"t1","thread_name":"Codex Thread","updated_at":"2026-05-02T00:00:00Z"}\n',
        encoding="utf-8",
    )
    (tmp_path / ".codex-global-state.json").write_text(
        (
            '{\n'
            '  "projectless-thread-ids": ["local:t1", "keep"],\n'
            '  "thread-workspace-root-hints": {"t1": "/tmp/project", "keep": "/tmp/keep"},\n'
            '  "electron-persisted-atom-state": {"prompt-history": {"t1": ["delete me"], "keep": ["keep me"]}}\n'
            '}\n'
        ),
        encoding="utf-8",
    )
    adapter = SQLiteStorageAdapter(db_path, BackupStore(tmp_path / "backups"))

    result = adapter.delete_local(SessionRef(session_id="t1", title="Codex Thread"))

    assert result.status == DeleteStatus.LOCAL_DELETED
    assert '"id":"t1"' not in (tmp_path / "session_index.jsonl").read_text(encoding="utf-8")
    assert '"id":"keep"' in (tmp_path / "session_index.jsonl").read_text(encoding="utf-8")
    global_state = (tmp_path / ".codex-global-state.json").read_text(encoding="utf-8")
    assert "local:t1" not in global_state
    assert '"t1"' not in global_state
    assert "keep" in global_state


def test_delete_codex_thread_schema_uses_codex_home_for_sidecars_when_db_is_under_sqlite(tmp_path):
    home = tmp_path / ".codex"
    db_path = home / "sqlite" / "state_5.sqlite"
    rollout_path = home / "sessions" / "2026" / "05" / "rollout.jsonl"
    db_path.parent.mkdir(parents=True)
    rollout_path.parent.mkdir(parents=True)
    rollout_path.write_text('{"type":"message"}\n', encoding="utf-8")
    create_codex_thread_db(db_path, rollout_path)
    (home / "session_index.jsonl").write_text(
        '{"id":"t1","thread_name":"Codex Thread","updated_at":"2026-05-02T00:00:00Z"}\n',
        encoding="utf-8",
    )
    (home / ".codex-global-state.json").write_text(
        '{"projectless-thread-ids":["t1"],"thread-workspace-root-hints":{"t1":"/tmp/project"}}\n',
        encoding="utf-8",
    )
    adapter = SQLiteStorageAdapter(db_path, BackupStore(tmp_path / "backups"))

    result = adapter.delete_local(SessionRef(session_id="t1", title="Codex Thread"))

    assert result.status == DeleteStatus.LOCAL_DELETED
    assert (home / "session_index.jsonl").read_text(encoding="utf-8") == ""
    assert "t1" not in (home / ".codex-global-state.json").read_text(encoding="utf-8")
    assert not (home / "sqlite" / "session_index.jsonl").exists()


def test_delete_codex_thread_schema_removes_thread_objects_from_global_state_lists(tmp_path):
    db_path = tmp_path / "state_5.sqlite"
    rollout_path = tmp_path / "rollout.jsonl"
    rollout_path.write_text('{"type":"message"}\n', encoding="utf-8")
    create_codex_thread_db(db_path, rollout_path)
    (tmp_path / ".codex-global-state.json").write_text(
        json.dumps(
            {
                "project-thread-order": [
                    {"id": "local:t1", "title": "Codex Thread"},
                    {"threadId": "keep", "title": "Keep"},
                ],
                "thread-recents": [
                    {"session_id": "t1", "label": "Codex Thread"},
                    {"sessionId": "keep", "label": "Keep"},
                ],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    adapter = SQLiteStorageAdapter(db_path, BackupStore(tmp_path / "backups"))

    result = adapter.delete_local(SessionRef(session_id="t1", title="Codex Thread"))

    assert result.status == DeleteStatus.LOCAL_DELETED
    state = json.loads((tmp_path / ".codex-global-state.json").read_text(encoding="utf-8"))
    assert state["project-thread-order"] == [{"threadId": "keep", "title": "Keep"}]
    assert state["thread-recents"] == [{"sessionId": "keep", "label": "Keep"}]


def test_delete_codex_thread_schema_removes_unused_workspace_roots(tmp_path):
    db_path = tmp_path / "state_5.sqlite"
    rollout_path = tmp_path / "rollout.jsonl"
    rollout_path.write_text('{"type":"message"}\n', encoding="utf-8")
    create_codex_thread_db(db_path, rollout_path)
    with sqlite3.connect(db_path) as db:
        db.execute("ALTER TABLE threads ADD COLUMN cwd TEXT")
        db.execute("UPDATE threads SET cwd = '/tmp/project' WHERE id = 't1'")
    (tmp_path / ".codex-global-state.json").write_text(
        '{"project-order":["/tmp/project","/keep"],"electron-saved-workspace-roots":["/tmp/project","/keep"]}\n',
        encoding="utf-8",
    )
    adapter = SQLiteStorageAdapter(db_path, BackupStore(tmp_path / "backups"))

    result = adapter.delete_local(SessionRef(session_id="t1", title="Codex Thread"))

    assert result.status == DeleteStatus.LOCAL_DELETED
    state = (tmp_path / ".codex-global-state.json").read_text(encoding="utf-8")
    assert "/tmp/project" not in state
    assert "/keep" in state


def test_delete_codex_thread_schema_keeps_workspace_root_used_by_other_thread(tmp_path):
    db_path = tmp_path / "state_5.sqlite"
    rollout_path = tmp_path / "rollout.jsonl"
    rollout_path.write_text('{"type":"message"}\n', encoding="utf-8")
    create_codex_thread_db(db_path, rollout_path)
    with sqlite3.connect(db_path) as db:
        db.execute("ALTER TABLE threads ADD COLUMN cwd TEXT")
        db.execute("UPDATE threads SET cwd = '/tmp/project' WHERE id = 't1'")
        db.execute("INSERT INTO threads (id, rollout_path, title, archived, archived_at, cwd) VALUES ('t2', '', 'Other', 0, NULL, '/tmp/project')")
    (tmp_path / ".codex-global-state.json").write_text(
        '{"project-order":["/tmp/project"],"electron-saved-workspace-roots":["/tmp/project"]}\n',
        encoding="utf-8",
    )
    adapter = SQLiteStorageAdapter(db_path, BackupStore(tmp_path / "backups"))

    result = adapter.delete_local(SessionRef(session_id="t1", title="Codex Thread"))

    assert result.status == DeleteStatus.LOCAL_DELETED
    state = (tmp_path / ".codex-global-state.json").read_text(encoding="utf-8")
    assert "/tmp/project" in state


def test_delete_codex_thread_schema_finds_rollout_file_by_session_meta_id(tmp_path):
    db_path = tmp_path / "state_5.sqlite"
    stale_rollout_path = tmp_path / "missing-rollout.jsonl"
    create_codex_thread_db(db_path, stale_rollout_path)
    session_file = tmp_path / "sessions" / "2026" / "05" / "12" / "rollout-2026-05-12T00-00-00-t1.jsonl"
    session_file.parent.mkdir(parents=True)
    session_file.write_text(
        '{"type":"session_meta","payload":{"id":"t1","cwd":"/tmp/project"}}\n'
        '{"type":"message","payload":{"text":"hello"}}\n',
        encoding="utf-8",
    )
    adapter = SQLiteStorageAdapter(db_path, BackupStore(tmp_path / "backups"))

    result = adapter.delete_local(SessionRef(session_id="local:t1", title="Codex Thread"))

    assert result.status == DeleteStatus.LOCAL_DELETED
    assert not session_file.exists()


def test_delete_codex_thread_schema_finds_archived_rollout_file_by_session_meta_id(tmp_path):
    db_path = tmp_path / "state_5.sqlite"
    stale_rollout_path = tmp_path / "missing-rollout.jsonl"
    create_codex_thread_db(db_path, stale_rollout_path)
    session_file = tmp_path / "archived_sessions" / "2026" / "05" / "12" / "rollout-2026-05-12T00-00-00-t1.jsonl"
    session_file.parent.mkdir(parents=True)
    session_file.write_text('{"type":"session_meta","payload":{"id":"t1","cwd":"/tmp/project"}}\n', encoding="utf-8")
    adapter = SQLiteStorageAdapter(db_path, BackupStore(tmp_path / "backups"))

    result = adapter.delete_local(SessionRef(session_id="local:t1", title="Codex Thread"))

    assert result.status == DeleteStatus.LOCAL_DELETED
    assert not session_file.exists()


def test_delete_automation_run_schema_creates_backup_and_can_undo(tmp_path):
    db_path = tmp_path / "codex-dev.db"
    with sqlite3.connect(db_path) as db:
        db.execute("CREATE TABLE automation_runs (thread_id TEXT NOT NULL, thread_title TEXT, status TEXT)")
        db.execute("INSERT INTO automation_runs (thread_id, thread_title, status) VALUES ('t1', 'Automation Thread', 'complete')")
    adapter = SQLiteStorageAdapter(db_path, BackupStore(tmp_path / "backups"))

    deleted = adapter.delete_local(SessionRef(session_id="local:t1", title="Automation Thread"))

    assert deleted.status == DeleteStatus.LOCAL_DELETED
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT COUNT(*) FROM automation_runs WHERE thread_id = 't1'").fetchone()[0] == 0

    restored = adapter.undo(deleted.undo_token or "")

    assert restored.status == DeleteStatus.UNDONE
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT status FROM automation_runs WHERE thread_id = 't1'").fetchone()[0] == "complete"


def test_delete_codex_thread_schema_removes_sidecar_only_ghost_thread(tmp_path):
    db_path = tmp_path / "state_5.sqlite"
    rollout_path = tmp_path / "other-rollout.jsonl"
    create_codex_thread_db(db_path, rollout_path)
    with sqlite3.connect(db_path) as db:
        db.execute("DELETE FROM threads WHERE id = 't1'")
    session_file = tmp_path / "sessions" / "2026" / "05" / "12" / "rollout-ghost.jsonl"
    session_file.parent.mkdir(parents=True)
    session_file.write_text('{"type":"session_meta","payload":{"id":"t1"}}\n', encoding="utf-8")
    (tmp_path / "session_index.jsonl").write_text(
        '{"id":"t1","thread_name":"Ghost","updated_at":"2026-05-02T00:00:00Z"}\n',
        encoding="utf-8",
    )
    (tmp_path / ".codex-global-state.json").write_text(
        '{"thread-workspace-root-hints":{"t1":"/tmp/project"}}\n',
        encoding="utf-8",
    )
    adapter = SQLiteStorageAdapter(db_path, BackupStore(tmp_path / "backups"))

    result = adapter.delete_local(SessionRef(session_id="t1", title="Ghost"))

    assert result.status == DeleteStatus.LOCAL_DELETED
    assert (tmp_path / "session_index.jsonl").read_text(encoding="utf-8") == ""
    assert "t1" not in (tmp_path / ".codex-global-state.json").read_text(encoding="utf-8")
    assert not session_file.exists()


def test_delete_codex_thread_schema_keeps_unknown_missing_thread_failed(tmp_path):
    db_path = tmp_path / "state_5.sqlite"
    rollout_path = tmp_path / "other-rollout.jsonl"
    create_codex_thread_db(db_path, rollout_path)
    with sqlite3.connect(db_path) as db:
        db.execute("DELETE FROM threads WHERE id = 't1'")
    adapter = SQLiteStorageAdapter(db_path, BackupStore(tmp_path / "backups"))

    result = adapter.delete_local(SessionRef(session_id="t1", title="Ghost"))

    assert result.status == DeleteStatus.FAILED
    assert "Thread not found" in result.message


def test_undo_restores_deleted_codex_thread_schema_and_rollout_file(tmp_path):
    db_path = tmp_path / "state_5.sqlite"
    rollout_path = tmp_path / "rollout.jsonl"
    rollout_path.write_text('{"type":"message"}\n', encoding="utf-8")
    create_codex_thread_db(db_path, rollout_path)
    adapter = SQLiteStorageAdapter(db_path, BackupStore(tmp_path / "backups"))
    deleted = adapter.delete_local(SessionRef(session_id="t1", title="Codex Thread"))

    restored = adapter.undo(deleted.undo_token or "")

    assert restored.status == DeleteStatus.UNDONE
    assert rollout_path.read_text(encoding="utf-8") == '{"type":"message"}\n'
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT title FROM threads WHERE id = 't1'").fetchone()[0] == "Codex Thread"
        assert db.execute("SELECT tool_name FROM thread_dynamic_tools WHERE thread_id = 't1'").fetchone()[0] == "Read"
        assert db.execute("SELECT goal FROM thread_goals WHERE thread_id = 't1'").fetchone()[0] == "delete me"
        assert db.execute("SELECT COUNT(*) FROM thread_spawn_edges WHERE parent_thread_id = 't1' OR child_thread_id = 't1'").fetchone()[0] == 2
        assert db.execute("SELECT output FROM stage1_outputs WHERE thread_id = 't1'").fetchone()[0] == "cached"
        assert db.execute("SELECT assigned_thread_id FROM agent_job_items WHERE id = 'job1'").fetchone()[0] == "t1"


def test_undo_restores_deleted_codex_sidecar_indexes(tmp_path):
    db_path = tmp_path / "state_5.sqlite"
    rollout_path = tmp_path / "rollout.jsonl"
    rollout_path.write_text('{"type":"message"}\n', encoding="utf-8")
    create_codex_thread_db(db_path, rollout_path)
    original_index = '{"id":"t1","thread_name":"Codex Thread","updated_at":"2026-05-02T00:00:00Z"}\n'
    original_global_state = '{"projectless-thread-ids":["t1"],"thread-workspace-root-hints":{"t1":"/tmp/project"}}\n'
    (tmp_path / "session_index.jsonl").write_text(original_index, encoding="utf-8")
    (tmp_path / ".codex-global-state.json").write_text(original_global_state, encoding="utf-8")
    adapter = SQLiteStorageAdapter(db_path, BackupStore(tmp_path / "backups"))
    deleted = adapter.delete_local(SessionRef(session_id="t1", title="Codex Thread"))

    restored = adapter.undo(deleted.undo_token or "")

    assert restored.status == DeleteStatus.UNDONE
    assert (tmp_path / "session_index.jsonl").read_text(encoding="utf-8") == original_index
    assert (tmp_path / ".codex-global-state.json").read_text(encoding="utf-8") == original_global_state


def test_delete_codex_thread_schema_accepts_local_prefixed_thread_id(tmp_path):
    db_path = tmp_path / "state_5.sqlite"
    rollout_path = tmp_path / "rollout.jsonl"
    rollout_path.write_text('{"type":"message"}\n', encoding="utf-8")
    create_codex_thread_db(db_path, rollout_path)
    adapter = SQLiteStorageAdapter(db_path, BackupStore(tmp_path / "backups"))

    result = adapter.delete_local(SessionRef(session_id="local:t1", title="Codex Thread"))

    assert result.status == DeleteStatus.LOCAL_DELETED
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT COUNT(*) FROM threads WHERE id = 't1'").fetchone()[0] == 0


def test_find_archived_codex_thread_by_title(tmp_path):
    db_path = tmp_path / "state_5.sqlite"
    rollout_path = tmp_path / "archived.jsonl"
    create_codex_thread_db(db_path, rollout_path)
    with sqlite3.connect(db_path) as db:
        db.execute("UPDATE threads SET archived = 1, archived_at = 123 WHERE id = 't1'")
    adapter = SQLiteStorageAdapter(db_path, BackupStore(tmp_path / "backups"))

    session = adapter.find_archived_thread_by_title("Codex Thread")

    assert session == SessionRef(session_id="t1", title="Codex Thread")


def test_find_archived_codex_thread_by_title_matches_rendered_archive_card_text(tmp_path):
    db_path = tmp_path / "state_5.sqlite"
    rollout_path = tmp_path / "archived.jsonl"
    create_codex_thread_db(db_path, rollout_path)
    with sqlite3.connect(db_path) as db:
        db.execute("UPDATE threads SET archived = 1, archived_at = 123 WHERE id = 't1'")
    adapter = SQLiteStorageAdapter(db_path, BackupStore(tmp_path / "backups"))

    session = adapter.find_archived_thread_by_title("Codex Thread 2026年5月9日，1:19 · RustGUI")

    assert session == SessionRef(session_id="t1", title="Codex Thread")


def test_find_archived_codex_thread_by_title_ignores_active_threads(tmp_path):
    db_path = tmp_path / "state_5.sqlite"
    rollout_path = tmp_path / "active.jsonl"
    create_codex_thread_db(db_path, rollout_path)
    adapter = SQLiteStorageAdapter(db_path, BackupStore(tmp_path / "backups"))

    session = adapter.find_archived_thread_by_title("Codex Thread")

    assert session is None


def test_delete_codex_thread_schema_reports_rollout_delete_failure(tmp_path, monkeypatch):
    db_path = tmp_path / "state_5.sqlite"
    rollout_path = tmp_path / "rollout.jsonl"
    rollout_path.write_text('{"type":"message"}\n', encoding="utf-8")
    create_codex_thread_db(db_path, rollout_path)
    adapter = SQLiteStorageAdapter(db_path, BackupStore(tmp_path / "backups"))

    def fail_unlink(self, missing_ok=False):
        if self == rollout_path:
            raise PermissionError("Access is denied")
        return original_unlink(self, missing_ok=missing_ok)

    original_unlink = type(rollout_path).unlink
    monkeypatch.setattr(type(rollout_path), "unlink", fail_unlink)

    result = adapter.delete_local(SessionRef(session_id="t1", title="Codex Thread"))

    assert result.status == DeleteStatus.FAILED
    assert "本地数据库已删除" in result.message
    assert "文件删除失败" in result.message
    assert "Access is denied" in result.message


def test_delete_local_session_uses_chinese_success_message(tmp_path):
    db_path = tmp_path / "codex.sqlite"
    create_supported_db(db_path)
    adapter = SQLiteStorageAdapter(db_path, BackupStore(tmp_path / "backups"))

    result = adapter.delete_local(SessionRef(session_id="s1", title="First"))

    assert result.message == "已从本地存储删除"


def test_move_codex_thread_workspace_updates_database_rollout_and_global_state(tmp_path):
    db_path = tmp_path / "state_5.sqlite"
    rollout_path = tmp_path / "rollout.jsonl"
    rollout_path.write_text(
        '{"type":"session_meta","payload":{"id":"t1","cwd":"/old/project","title":"Codex Thread"}}\n'
        '{"type":"session_meta","payload":{"id":"other","cwd":"/old/project"}}\n'
        '{"type":"message","payload":{"text":"hello"}}\n',
        encoding="utf-8",
    )
    create_codex_thread_db(db_path, rollout_path)
    with sqlite3.connect(db_path) as db:
        db.execute("ALTER TABLE threads ADD COLUMN cwd TEXT")
        db.execute("ALTER TABLE threads ADD COLUMN updated_at INTEGER")
        db.execute("ALTER TABLE threads ADD COLUMN updated_at_ms INTEGER")
        db.execute("ALTER TABLE threads ADD COLUMN created_at_ms INTEGER")
        db.execute(
            "UPDATE threads SET cwd = '/old/project', updated_at = 100, updated_at_ms = 100000, created_at_ms = 90000 WHERE id = 't1'"
        )
    (tmp_path / ".codex-global-state.json").write_text(
        json.dumps(
            {
                "projectless-thread-ids": ["local:t1", "keep"],
                "thread-workspace-root-hints": {"local:t1": "/old/project", "t1": "/old/project", "keep": "/keep"},
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    adapter = SQLiteStorageAdapter(db_path, BackupStore(tmp_path / "backups"))

    result = adapter.move_codex_thread_workspace(SessionRef(session_id="local:t1", title="Codex Thread"), "/new/project")

    assert result["status"] == "moved"
    assert result["session_id"] == "t1"
    assert result["previous_cwd"] == "/old/project"
    assert result["target_cwd"] == "/new/project"
    assert result["rollout_updated"] is True
    assert result["updated_at"] == 100
    assert result["updated_at_ms"] == 100000
    assert result["created_at_ms"] == 90000
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT cwd FROM threads WHERE id = 't1'").fetchone()[0] == "/new/project"
    rollout_lines = [json.loads(line) for line in rollout_path.read_text(encoding="utf-8").splitlines()]
    assert rollout_lines[0]["payload"]["cwd"] == "/new/project"
    assert rollout_lines[1]["payload"]["cwd"] == "/old/project"
    state = json.loads((tmp_path / ".codex-global-state.json").read_text(encoding="utf-8"))
    assert state["projectless-thread-ids"] == ["keep"]
    assert state["thread-workspace-root-hints"]["t1"] == "/new/project"
    assert "local:t1" not in state["thread-workspace-root-hints"]


def test_move_codex_thread_projectless_clears_workspace_and_marks_projectless(tmp_path):
    db_path = tmp_path / "state_5.sqlite"
    rollout_path = tmp_path / "rollout.jsonl"
    rollout_path.write_text('{"type":"session_meta","payload":{"id":"t1","cwd":"/old/project"}}\n', encoding="utf-8")
    create_codex_thread_db(db_path, rollout_path)
    with sqlite3.connect(db_path) as db:
        db.execute("ALTER TABLE threads ADD COLUMN cwd TEXT")
        db.execute("UPDATE threads SET cwd = '/old/project' WHERE id = 't1'")
    (tmp_path / ".codex-global-state.json").write_text(
        '{"projectless-thread-ids":["keep"],"thread-workspace-root-hints":{"t1":"/old/project","local:t1":"/old/project","keep":"/keep"}}\n',
        encoding="utf-8",
    )
    adapter = SQLiteStorageAdapter(db_path, BackupStore(tmp_path / "backups"))

    result = adapter.move_codex_thread_projectless(SessionRef(session_id="t1", title="Codex Thread"))

    assert result["status"] == "moved"
    assert result["session_id"] == "t1"
    assert result["previous_cwd"] == "/old/project"
    assert result["target_cwd"] == ""
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT cwd FROM threads WHERE id = 't1'").fetchone()[0] == ""
    assert json.loads(rollout_path.read_text(encoding="utf-8").strip())["payload"]["cwd"] == ""
    state = json.loads((tmp_path / ".codex-global-state.json").read_text(encoding="utf-8"))
    assert state["projectless-thread-ids"] == ["keep", "t1"]
    assert "t1" not in state["thread-workspace-root-hints"]
    assert "local:t1" not in state["thread-workspace-root-hints"]


def test_codex_thread_sort_keys_return_timestamp_payloads(tmp_path):
    db_path = tmp_path / "state_5.sqlite"
    rollout_path = tmp_path / "rollout.jsonl"
    create_codex_thread_db(db_path, rollout_path)
    with sqlite3.connect(db_path) as db:
        db.execute("ALTER TABLE threads ADD COLUMN updated_at INTEGER")
        db.execute("ALTER TABLE threads ADD COLUMN updated_at_ms INTEGER")
        db.execute("ALTER TABLE threads ADD COLUMN created_at_ms INTEGER")
        db.execute("UPDATE threads SET updated_at = 100, updated_at_ms = 100000, created_at_ms = 90000 WHERE id = 't1'")
        db.execute(
            "INSERT INTO threads (id, rollout_path, title, archived, archived_at, updated_at, updated_at_ms, created_at_ms) VALUES ('t2', '', 'Second', 0, NULL, 200, 200000, 190000)"
        )
    adapter = SQLiteStorageAdapter(db_path, BackupStore(tmp_path / "backups"))

    assert adapter.codex_thread_sort_key(SessionRef(session_id="local:t1", title="Codex Thread")) == {
        "status": "ok",
        "session_id": "t1",
        "updated_at": 100,
        "updated_at_ms": 100000,
        "created_at_ms": 90000,
    }
    assert adapter.codex_thread_sort_keys(
        [SessionRef(session_id="local:t2", title="Second"), SessionRef(session_id="local:t1", title="Codex Thread")]
    ) == {
        "status": "ok",
        "sort_keys": [
            {"session_id": "t2", "updated_at": 200, "updated_at_ms": 200000, "created_at_ms": 190000},
            {"session_id": "t1", "updated_at": 100, "updated_at_ms": 100000, "created_at_ms": 90000},
        ],
    }


def test_delete_unsupported_schema_fails(tmp_path):
    db_path = tmp_path / "unknown.sqlite"
    with sqlite3.connect(db_path) as db:
        db.execute("CREATE TABLE unrelated (id TEXT PRIMARY KEY)")
    adapter = SQLiteStorageAdapter(db_path, BackupStore(tmp_path / "backups"))

    result = adapter.delete_local(SessionRef(session_id="s1", title="First"))

    assert result.status == DeleteStatus.FAILED
    assert "Unsupported" in result.message
