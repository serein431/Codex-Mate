import sqlite3

from codex_mate.models import SessionRef
from codex_mate.rollout_reader import read_thread_rollout


def create_thread_db(path, rollout_path):
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE threads (id TEXT PRIMARY KEY, title TEXT, rollout_path TEXT)")
        db.execute(
            "INSERT INTO threads (id, title, rollout_path) VALUES ('t1', 'Thread One', ?)",
            (str(rollout_path),),
        )


def test_rollout_reader_reads_thread_and_rollout_messages(tmp_path):
    rollout = tmp_path / "rollout.jsonl"
    rollout.write_text(
        '{"type":"response_item","timestamp":"2026-05-23T08:00:00Z","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"你好"}]}}\n'
        '{"type":"response_item","timestamp":"2026-05-23T08:00:01Z","payload":{"type":"message","role":"assistant","content":[{"type":"output_text","text":"我在。"}]}}\n'
        '{"type":"event_msg","payload":{"message":"ignored"}}\n'
        '{"type":"response_item","timestamp":"2026-05-23T08:00:02Z","payload":{"type":"message","role":"system","content":[{"type":"text","text":"hidden"}]}}\n'
        '{"type":"response_item","timestamp":"2026-05-23T08:00:03Z","payload":{"type":"message","role":"user","content":[{"type":"input_image","image_url":"data:image/png;base64,AAA"}]}}\n',
        encoding="utf-8",
    )
    db_path = tmp_path / "state_5.sqlite"
    create_thread_db(db_path, rollout)

    result = read_thread_rollout(db_path, SessionRef(session_id="local:t1", title="Fallback"))

    assert result.status == "ready"
    assert result.session_id == "t1"
    assert result.title == "Thread One"
    assert result.rollout_path == str(rollout)
    assert [(message.role, message.speaker, message.message_index, message.body) for message in result.messages] == [
        ("user", "User", 0, "你好"),
        ("assistant", "Assistant", 1, "我在。"),
        ("user", "User", 3, "> Image attachment"),
    ]
    assert result.messages[0].timestamp == "2026-05-23 16:00:00"


def test_rollout_reader_keeps_empty_user_message_for_timeline(tmp_path):
    rollout = tmp_path / "rollout.jsonl"
    rollout.write_text(
        '{"type":"response_item","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":""}]}}\n',
        encoding="utf-8",
    )
    db_path = tmp_path / "state_5.sqlite"
    create_thread_db(db_path, rollout)

    result = read_thread_rollout(db_path, SessionRef(session_id="t1", title="Fallback"))

    assert result.status == "ready"
    assert len(result.messages) == 1
    assert result.messages[0].role == "user"
    assert result.messages[0].body == ""


def test_rollout_reader_reports_missing_database(tmp_path):
    missing_db = tmp_path / "missing.sqlite"

    result = read_thread_rollout(missing_db, SessionRef(session_id="t1", title="First"))

    assert result.status == "failed"
    assert result.message == f"数据库不存在：{missing_db}"


def test_rollout_reader_reports_unsupported_schema(tmp_path):
    db_path = tmp_path / "state_5.sqlite"
    with sqlite3.connect(db_path) as db:
        db.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY)")

    result = read_thread_rollout(db_path, SessionRef(session_id="t1", title="First"))

    assert result.status == "failed"
    assert result.message == "不支持当前本地存储结构"


def test_rollout_reader_reports_invalid_rollout_json(tmp_path):
    rollout = tmp_path / "rollout.jsonl"
    rollout.write_text("{bad json}\n", encoding="utf-8")
    db_path = tmp_path / "state_5.sqlite"
    create_thread_db(db_path, rollout)

    result = read_thread_rollout(db_path, SessionRef(session_id="t1", title="First"))

    assert result.status == "failed"
    assert result.message.startswith("读取 rollout 失败：")
