from __future__ import annotations

from pathlib import Path

from codex_mate.models import SessionRef
from codex_mate.rollout_reader import RolloutMessage, collapse_whitespace, read_thread_rollout


PREVIEW_LIMIT = 40


class ConversationTimelineService:
    def __init__(self, db_path: Path | None):
        self.db_path = db_path

    def timeline(self, session: SessionRef) -> dict[str, object]:
        result = read_thread_rollout(self.db_path, session)
        if result.status != "ready":
            return {
                "status": "failed",
                "message": result.message,
                "session_id": result.session_id,
                "title": result.title,
                "message_count": 0,
                "items": [],
            }

        user_messages = [message for message in result.messages if message.role == "user"]
        if not user_messages:
            return {
                "status": "empty",
                "message": "未找到用户消息",
                "session_id": result.session_id,
                "title": result.title,
                "message_count": 0,
                "items": [],
            }

        return {
            "status": "ready",
            "message": "已读取完整对话目录",
            "session_id": result.session_id,
            "title": result.title,
            "message_count": len(user_messages),
            "items": [_timeline_item(message, index, len(user_messages)) for index, message in enumerate(user_messages)],
        }


def _timeline_item(message: RolloutMessage, index: int, total: int) -> dict[str, object]:
    return {
        "id": f"u-{index + 1:04d}",
        "index": index,
        "message_index": message.message_index,
        "timestamp": message.timestamp,
        "text": message.body,
        "preview": timeline_preview(message.body),
        "percent": timeline_percent(index, total),
    }


def timeline_percent(index: int, total: int) -> float:
    if total <= 1:
        return 50.0
    return round((index / (total - 1)) * 100, 3)


def timeline_preview(text: str) -> str:
    if "> Image attachment" in text or text.strip() == "Image attachment":
        return "Image attachment"
    normalized = collapse_whitespace(text.replace("> Image attachment", "Image attachment").replace("[Image link]", ""))
    normalized = normalized.replace("(<", "").replace(">)", "").strip()
    if not normalized:
        return "空消息"
    chars = list(normalized)
    if len(chars) <= PREVIEW_LIMIT:
        return normalized
    return "".join(chars[:PREVIEW_LIMIT]).rstrip() + "…"
