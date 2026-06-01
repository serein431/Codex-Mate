import sqlite3

from codex_mate.conversation_timeline import ConversationTimelineService
from codex_mate.models import SessionRef


def create_thread_db(path, rollout_path):
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE threads (id TEXT PRIMARY KEY, title TEXT, rollout_path TEXT)")
        db.execute(
            "INSERT INTO threads (id, title, rollout_path) VALUES ('t1', 'Long Thread', ?)",
            (str(rollout_path),),
        )


def test_conversation_timeline_returns_complete_user_message_directory(tmp_path):
    rollout = tmp_path / "rollout.jsonl"
    rollout.write_text(
        '{"type":"response_item","timestamp":"2026-05-23T08:00:00Z","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"第一条用户问题"}]}}\n'
        '{"type":"response_item","timestamp":"2026-05-23T08:00:01Z","payload":{"type":"message","role":"assistant","content":[{"type":"output_text","text":"回答不进目录"}]}}\n'
        '{"type":"response_item","timestamp":"2026-05-23T08:00:02Z","payload":{"type":"message","role":"developer","content":[{"type":"text","text":"hidden"}]}}\n'
        '{"type":"response_item","timestamp":"2026-05-23T08:00:03Z","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"第二条用户问题"},{"type":"input_image","image_url":"https://example.test/a.png"}]}}\n',
        encoding="utf-8",
    )
    db_path = tmp_path / "state_5.sqlite"
    create_thread_db(db_path, rollout)

    payload = ConversationTimelineService(db_path).timeline(SessionRef(session_id="local:t1", title="Fallback"))

    assert payload["status"] == "ready"
    assert payload["session_id"] == "t1"
    assert payload["title"] == "Long Thread"
    assert payload["message_count"] == 2
    assert [item["id"] for item in payload["items"]] == ["u-0001", "u-0002"]
    assert [item["index"] for item in payload["items"]] == [0, 1]
    assert [item["message_index"] for item in payload["items"]] == [0, 3]
    assert [item["percent"] for item in payload["items"]] == [0.0, 100.0]
    assert payload["items"][0]["text"] == "第一条用户问题"
    assert payload["items"][1]["preview"] == "第二条用户问题"
    assert "Image attachment" not in payload["items"][1]["preview"]
    assert payload["items"][1]["timestamp"] == "2026-05-23 16:00:03"


def test_conversation_timeline_filters_non_user_visible_placeholders(tmp_path):
    rollout = tmp_path / "rollout.jsonl"
    rollout.write_text(
        '{"type":"response_item","timestamp":"2026-05-23T08:00:00Z","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"真正的问题"}]}}\n'
        '{"type":"response_item","timestamp":"2026-05-23T08:00:01Z","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":""}]}}\n'
        '{"type":"response_item","timestamp":"2026-05-23T08:00:02Z","payload":{"type":"message","role":"user","content":[{"type":"input_image","image_url":"https://example.test/a.png"}]}}\n'
        '{"type":"response_item","timestamp":"2026-05-23T08:00:03Z","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"The user interrupted the previous response."}]}}\n'
        '{"type":"response_item","timestamp":"2026-05-23T08:00:04Z","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"<turn_aborted> The user interrupted the previous turn on purpose."}]}}\n'
        '{"type":"response_item","timestamp":"2026-05-23T08:00:05Z","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"<environment_context><current_date>2026-05-23</current_date><timezone>Asia/.现在还会有这种"}]}}\n'
        '{"type":"response_item","timestamp":"2026-05-23T08:00:06Z","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"# AGENTS.md instructions for /tmp/project\\n\\n<INSTRUCTIONS>hidden</INSTRUCTIONS>"}]}}\n'
        '{"type":"response_item","timestamp":"2026-05-23T08:00:07Z","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"Another language model started to solve this problem and produced a summary of its thinking process."}]}}\n'
        '{"type":"response_item","timestamp":"2026-05-23T08:00:08Z","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"预览里出现 the user interrupted 这句话"}]}}\n',
        encoding="utf-8",
    )
    db_path = tmp_path / "state_5.sqlite"
    create_thread_db(db_path, rollout)

    payload = ConversationTimelineService(db_path).timeline(SessionRef(session_id="t1", title="Fallback"))

    assert payload["status"] == "ready"
    assert payload["message_count"] == 2
    assert [item["preview"] for item in payload["items"]] == ["真正的问题", "预览里出现 the user interrupted 这句话"]


def test_conversation_timeline_returns_turn_id_for_precise_dom_targeting(tmp_path):
    rollout = tmp_path / "rollout.jsonl"
    rollout.write_text(
        '{"type":"event_msg","payload":{"type":"task_started","turn_id":"turn-1"}}\n'
        '{"type":"response_item","timestamp":"2026-05-23T08:00:00Z","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"第一条"}]}}\n'
        '{"type":"event_msg","payload":{"type":"task_started","turn_id":"turn-2"}}\n'
        '{"type":"response_item","timestamp":"2026-05-23T08:01:00Z","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"第二条"}]}}\n',
        encoding="utf-8",
    )
    db_path = tmp_path / "state_5.sqlite"
    create_thread_db(db_path, rollout)

    payload = ConversationTimelineService(db_path).timeline(SessionRef(session_id="t1", title="Fallback"))

    assert [item["turn_id"] for item in payload["items"]] == ["turn-1", "turn-2"]


def test_conversation_timeline_reports_empty_when_no_user_messages(tmp_path):
    rollout = tmp_path / "rollout.jsonl"
    rollout.write_text(
        '{"type":"response_item","payload":{"type":"message","role":"assistant","content":[{"type":"output_text","text":"只有回答"}]}}\n',
        encoding="utf-8",
    )
    db_path = tmp_path / "state_5.sqlite"
    create_thread_db(db_path, rollout)

    payload = ConversationTimelineService(db_path).timeline(SessionRef(session_id="t1", title="Fallback"))

    assert payload["status"] == "empty"
    assert payload["message_count"] == 0
    assert payload["items"] == []
    assert payload["message"] == "未找到用户消息"


def test_conversation_timeline_reports_reader_failures(tmp_path):
    db_path = tmp_path / "missing.sqlite"

    payload = ConversationTimelineService(db_path).timeline(SessionRef(session_id="t1", title="Fallback"))

    assert payload["status"] == "failed"
    assert payload["message"] == f"数据库不存在：{db_path}"
