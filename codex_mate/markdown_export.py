from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from codex_mate.models import ExportResult, ExportStatus, SessionRef


class MarkdownExportService:
    def __init__(self, db_path: Path | None):
        self.db_path = db_path

    def export(self, session: SessionRef) -> ExportResult:
        if self.db_path is None:
            return _failed(session.session_id, "未配置本地 Codex 数据库")
        if not self.db_path.exists():
            return _failed(session.session_id, f"数据库不存在：{self.db_path}")

        thread_id = normalize_session_id(session.session_id)
        try:
            with sqlite3.connect(self.db_path) as db:
                db.row_factory = sqlite3.Row
                if not _supports_codex_threads(db):
                    return _failed(thread_id, "不支持当前本地存储结构")
                row = db.execute("SELECT id, title, rollout_path FROM threads WHERE id = ?", (thread_id,)).fetchone()
        except sqlite3.Error as exc:
            return _failed(thread_id, f"读取数据库失败：{exc}")

        if row is None:
            return _failed(thread_id, "未找到对应会话")

        title = display_title(str(row["title"] or session.title or ""))
        rollout_path = str(row["rollout_path"] or "")
        if not rollout_path:
            return _failed(thread_id, "会话缺少 rollout 文件路径")
        path = Path(rollout_path)
        if not path.is_file():
            return _failed(thread_id, f"rollout 文件不存在：{rollout_path}")

        try:
            messages = load_messages(path)
        except (OSError, json.JSONDecodeError) as exc:
            return _failed(thread_id, f"读取 rollout 失败：{exc}")
        if not messages:
            return _failed(thread_id, "未找到可导出的用户或助手消息")

        filename = build_filename(title, thread_id)
        return ExportResult(
            ExportStatus.EXPORTED,
            thread_id,
            f"已导出为 Markdown：{filename}",
            filename=filename,
            markdown=render_markdown(title, messages),
        )


@dataclass(frozen=True)
class Message:
    speaker: str
    timestamp: str | None
    body: str


def load_messages(path: Path) -> list[Message]:
    messages = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        event = json.loads(raw)
        if event.get("type") != "response_item":
            continue
        payload = event.get("payload")
        if not isinstance(payload, dict) or payload.get("type") != "message":
            continue
        role = payload.get("role")
        if role == "user":
            speaker = "User"
        elif role == "assistant":
            speaker = "Assistant"
        else:
            continue
        body = serialize_message_content(payload.get("content"))
        if body:
            messages.append(Message(speaker, format_timestamp(event.get("timestamp")), body))
    return messages


def serialize_message_content(content: Any) -> str:
    if isinstance(content, str):
        return normalize_newlines(content).strip()
    if not isinstance(content, list):
        return ""

    blocks = []
    for block in content:
        if isinstance(block, str):
            text = normalize_newlines(block).strip()
            if text:
                blocks.append(text)
            continue
        if not isinstance(block, dict):
            continue
        block_type = str(block.get("type") or "")
        if block_type in {"input_text", "output_text", "text"}:
            text = normalize_newlines(str(block.get("text") or "")).strip()
            if text:
                blocks.append(text)
        elif block_type == "input_image":
            image_url = str(block.get("image_url") or "").strip()
            if image_url and not image_url.startswith("data:"):
                blocks.append(f"> Image attachment\n[Image link](<{image_url}>)")
            else:
                blocks.append("> Image attachment")
    return "\n\n".join(blocks).strip()


def format_timestamp(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone().strftime("%Y-%m-%d %H:%M:%S")


def render_markdown(title: str, messages: list[Message]) -> str:
    lines = [f"# {title}", ""]
    for message in messages:
        lines.append(f"### {message.speaker}")
        if message.timestamp:
            lines.append(f"_{message.timestamp}_")
        lines.append("")
        lines.append(message.body.rstrip())
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_filename(title: str, thread_id: str) -> str:
    cleaned = collapse_whitespace(replace_windows_filename_chars(title, " ")).strip(" .")
    safe_title = cleaned[:80].strip(" .") or "Untitled session"
    safe_thread_id = replace_windows_filename_chars(thread_id, "-").strip()
    return f"{safe_title}-{safe_thread_id}.md"


def display_title(value: str) -> str:
    normalized = collapse_whitespace(normalize_newlines(value))
    return normalized or "Untitled session"


def normalize_session_id(session_id: str) -> str:
    return session_id.removeprefix("local:")


def normalize_newlines(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


def replace_windows_filename_chars(value: str, replacement: str) -> str:
    output = []
    for char in value:
        if char in '<>:"/\\|?*' or ord(char) < 32:
            output.append(replacement)
        else:
            output.append(char)
    return "".join(output)


def collapse_whitespace(value: str) -> str:
    return " ".join(value.split())


def _supports_codex_threads(db: sqlite3.Connection) -> bool:
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    if "threads" not in tables:
        return False
    columns = {row[1] for row in db.execute("PRAGMA table_info(threads)")}
    return {"id", "title", "rollout_path"}.issubset(columns)


def _failed(session_id: str, message: str) -> ExportResult:
    return ExportResult(ExportStatus.FAILED, session_id, message)
