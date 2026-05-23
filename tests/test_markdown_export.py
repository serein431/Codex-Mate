import sqlite3

from codex_mate.markdown_export import MarkdownExportService
from codex_mate.models import ExportStatus, SessionRef


def create_thread_db(path, rollout_path):
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE threads (id TEXT PRIMARY KEY, title TEXT, rollout_path TEXT)")
        db.execute(
            "INSERT INTO threads (id, title, rollout_path) VALUES ('t1', 'Bad:/Title', ?)",
            (str(rollout_path),),
        )


def test_markdown_export_reads_rollout_messages(tmp_path):
    rollout = tmp_path / "rollout.jsonl"
    rollout.write_text(
        '{"type":"response_item","timestamp":"2026-05-23T08:00:00Z","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"你好"}]}}\n'
        '{"type":"response_item","timestamp":"2026-05-23T08:00:03Z","payload":{"type":"message","role":"assistant","content":[{"type":"output_text","text":"我在。"}]}}\n',
        encoding="utf-8",
    )
    db_path = tmp_path / "state_5.sqlite"
    create_thread_db(db_path, rollout)

    result = MarkdownExportService(db_path).export(SessionRef(session_id="local:t1", title="Fallback"))

    assert result.status == ExportStatus.EXPORTED
    assert result.session_id == "t1"
    assert result.filename == "Bad Title-t1.md"
    assert "# Bad:/Title" in (result.markdown or "")
    assert "### User" in (result.markdown or "")
    assert "你好" in (result.markdown or "")
    assert "### Assistant" in (result.markdown or "")
    assert "我在。" in (result.markdown or "")


def test_markdown_export_reports_missing_thread(tmp_path):
    db_path = tmp_path / "state_5.sqlite"
    create_thread_db(db_path, tmp_path / "missing.jsonl")

    result = MarkdownExportService(db_path).export(SessionRef(session_id="missing", title="Missing"))

    assert result.status == ExportStatus.FAILED
    assert result.message == "未找到对应会话"


def test_markdown_export_rejects_unsupported_schema(tmp_path):
    db_path = tmp_path / "state_5.sqlite"
    with sqlite3.connect(db_path) as db:
        db.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY)")

    result = MarkdownExportService(db_path).export(SessionRef(session_id="t1", title="First"))

    assert result.status == ExportStatus.FAILED
    assert result.message == "不支持当前本地存储结构"
