from __future__ import annotations

import re
from pathlib import Path

from codex_mate.models import SessionRef
from codex_mate.rollout_reader import RolloutMessage, collapse_whitespace, normalize_newlines, read_thread_rollout


PREVIEW_LIMIT = 96
IMAGE_LINK_RE = re.compile(r"\[Image link\]\(<[^>]+>\)")
INTERNAL_USER_PLACEHOLDER_PREFIXES = (
    "the user interrupted",
    "the user has interrupted",
    "the user canceled",
    "the user cancelled",
    "the user stopped",
    "user interrupted",
)
INTERNAL_USER_CONTEXT_PREFIXES = (
    "<environment_context>",
    "<permissions instructions>",
    "<app-context>",
    "<collaboration_mode>",
    "<apps_instructions>",
    "<skills_instructions>",
    "<plugins_instructions>",
    "# agents.md instructions",
    "agents.md instructions for ",
    "another language model started to solve this problem",
)


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

        user_messages = [message for message in result.messages if is_timeline_user_message(message)]
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
    visible_text = timeline_visible_text(message.body)
    return {
        "id": f"u-{index + 1:04d}",
        "index": index,
        "message_index": message.message_index,
        "turn_id": message.turn_id,
        "timestamp": message.timestamp,
        "text": visible_text,
        "preview": timeline_preview(visible_text),
        "percent": timeline_percent(index, total),
    }


def timeline_percent(index: int, total: int) -> float:
    if total <= 1:
        return 50.0
    return round((index / (total - 1)) * 100, 3)


def timeline_preview(text: str) -> str:
    normalized = timeline_visible_text(text)
    if not normalized:
        return "空消息"
    chars = list(normalized)
    if len(chars) <= PREVIEW_LIMIT:
        return normalized
    return "".join(chars[:PREVIEW_LIMIT]).rstrip() + "…"


def is_timeline_user_message(message: RolloutMessage) -> bool:
    if message.role != "user":
        return False
    visible_text = timeline_visible_text(message.body)
    if not visible_text:
        return False
    return not is_internal_user_placeholder(visible_text)


def timeline_visible_text(text: str) -> str:
    lines: list[str] = []
    skip_next_image_link = False
    for raw_line in normalize_newlines(text).split("\n"):
        stripped = raw_line.strip()
        normalized = stripped.lstrip(">").strip().lower()
        if normalized == "image attachment":
            skip_next_image_link = True
            continue
        if skip_next_image_link and IMAGE_LINK_RE.fullmatch(stripped):
            skip_next_image_link = False
            continue
        skip_next_image_link = False
        lines.append(raw_line)
    return collapse_whitespace(IMAGE_LINK_RE.sub("", "\n".join(lines))).strip()


def is_internal_user_placeholder(text: str) -> bool:
    normalized = collapse_whitespace(text).lower()
    if normalized.startswith(INTERNAL_USER_CONTEXT_PREFIXES):
        return True
    without_leading_tags = re.sub(r"^(?:<[^>]+>\s*)+", "", normalized)
    return any(without_leading_tags.startswith(prefix) for prefix in INTERNAL_USER_PLACEHOLDER_PREFIXES)
