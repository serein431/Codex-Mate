from __future__ import annotations

from pathlib import Path

from codex_mate.models import ExportResult, ExportStatus, SessionRef
from codex_mate.rollout_reader import (
    RolloutMessage as Message,
    collapse_whitespace,
    display_title,
    format_timestamp,
    load_rollout_messages,
    normalize_newlines,
    normalize_session_id,
    read_thread_rollout,
    serialize_message_content,
)


class MarkdownExportService:
    def __init__(self, db_path: Path | None):
        self.db_path = db_path

    def export(self, session: SessionRef) -> ExportResult:
        result = read_thread_rollout(self.db_path, session)
        if result.status != "ready":
            return _failed(result.session_id, result.message)

        messages = [message for message in result.messages if message.body.strip()]
        if not messages:
            return _failed(result.session_id, "未找到可导出的用户或助手消息")

        filename = build_filename(result.title, result.session_id)
        return ExportResult(
            ExportStatus.EXPORTED,
            result.session_id,
            f"已导出为 Markdown：{filename}",
            filename=filename,
            markdown=render_markdown(result.title, messages),
        )


def load_messages(path: Path) -> list[Message]:
    return [message for message in load_rollout_messages(path) if message.body.strip()]


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


def replace_windows_filename_chars(value: str, replacement: str) -> str:
    output = []
    for char in value:
        if char in '<>:"/\\|?*' or ord(char) < 32:
            output.append(replacement)
        else:
            output.append(char)
    return "".join(output)


def _failed(session_id: str, message: str) -> ExportResult:
    return ExportResult(ExportStatus.FAILED, session_id, message)


__all__ = [
    "MarkdownExportService",
    "Message",
    "build_filename",
    "collapse_whitespace",
    "display_title",
    "format_timestamp",
    "load_messages",
    "normalize_newlines",
    "normalize_session_id",
    "render_markdown",
    "replace_windows_filename_chars",
    "serialize_message_content",
]
