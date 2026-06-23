from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from codex_mate import codex_storage
from codex_mate.models import SessionRef


@dataclass(frozen=True)
class RolloutMessage:
    role: str
    speaker: str
    timestamp: str | None
    body: str
    message_index: int
    turn_id: str = ""


@dataclass(frozen=True)
class RolloutReadResult:
    status: str
    session_id: str
    message: str
    title: str = "Untitled session"
    rollout_path: str | None = None
    messages: list[RolloutMessage] = field(default_factory=list)


def read_thread_rollout(db_path: Path | None, session: SessionRef) -> RolloutReadResult:
    thread_id = normalize_session_id(session.session_id)
    if db_path is None:
        return _failed(thread_id, "未配置本地 Codex 数据库", session.title)
    if not db_path.exists():
        return _failed(thread_id, f"数据库不存在：{db_path}", session.title)

    unsupported_schema = False
    last_error = ""
    for candidate in rollout_db_candidates(db_path):
        try:
            with sqlite3.connect(candidate) as db:
                db.row_factory = sqlite3.Row
                if not _supports_codex_threads(db):
                    unsupported_schema = True
                    continue
                row = db.execute("SELECT id, title, rollout_path FROM threads WHERE id = ?", (thread_id,)).fetchone()
        except sqlite3.Error as exc:
            last_error = str(exc)
            continue
        if row is not None:
            return read_rollout_row(thread_id, row, session)
    if last_error and not unsupported_schema:
        return _failed(thread_id, f"读取数据库失败：{last_error}", session.title)
    if unsupported_schema and not any_supports_codex_threads(rollout_db_candidates(db_path)):
        return _failed(thread_id, "不支持当前本地存储结构", session.title)
    return _failed(thread_id, "未找到对应会话", session.title)


def rollout_db_candidates(db_path: Path) -> list[Path]:
    paths = [db_path]
    home = codex_storage.codex_home_for_db_path(db_path)
    if home is not None:
        for candidate in codex_storage.discover_thread_db_paths(home):
            if candidate not in paths:
                paths.append(candidate)
    return paths


def any_supports_codex_threads(paths: list[Path]) -> bool:
    for path in paths:
        try:
            with sqlite3.connect(path) as db:
                if _supports_codex_threads(db):
                    return True
        except sqlite3.Error:
            continue
    return False


def read_rollout_row(thread_id: str, row: sqlite3.Row, session: SessionRef) -> RolloutReadResult:
    title = display_title(str(row["title"] or session.title or ""))
    rollout_path = str(row["rollout_path"] or "")
    if not rollout_path:
        return _failed(thread_id, "会话缺少 rollout 文件路径", title)
    path = Path(rollout_path)
    if not path.is_file():
        return _failed(thread_id, f"rollout 文件不存在：{rollout_path}", title)
    try:
        messages = load_rollout_messages(path)
    except (OSError, json.JSONDecodeError) as exc:
        return _failed(thread_id, f"读取 rollout 失败：{exc}", title)

    return RolloutReadResult("ready", thread_id, "已读取 rollout", title=title, rollout_path=rollout_path, messages=messages)


def load_rollout_messages(path: Path) -> list[RolloutMessage]:
    messages: list[RolloutMessage] = []
    message_index = -1
    current_turn_id = ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        event = json.loads(raw)
        payload = event.get("payload")
        if isinstance(payload, dict):
            turn_id = str(payload.get("turn_id") or "").strip()
            if turn_id:
                current_turn_id = turn_id
        if event.get("type") != "response_item":
            continue
        if not isinstance(payload, dict) or payload.get("type") != "message":
            continue
        message_index += 1
        role = str(payload.get("role") or "")
        if role == "user":
            speaker = "User"
        elif role == "assistant":
            speaker = "Assistant"
        else:
            continue
        content = payload.get("content")
        body = serialize_message_content(content)
        if body or has_known_message_content(content):
            messages.append(RolloutMessage(role, speaker, format_timestamp(event.get("timestamp")), body, message_index, current_turn_id))
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


def has_known_message_content(content: Any) -> bool:
    if isinstance(content, str):
        return True
    if not isinstance(content, list):
        return False
    for block in content:
        if isinstance(block, str):
            return True
        if isinstance(block, dict) and str(block.get("type") or "") in {"input_text", "output_text", "text", "input_image"}:
            return True
    return False


def format_timestamp(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone().strftime("%Y-%m-%d %H:%M:%S")


def display_title(value: str) -> str:
    normalized = collapse_whitespace(normalize_newlines(value))
    return normalized or "Untitled session"


def normalize_session_id(session_id: str) -> str:
    return session_id.removeprefix("local:")


def normalize_newlines(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


def collapse_whitespace(value: str) -> str:
    return " ".join(value.split())


def _supports_codex_threads(db: sqlite3.Connection) -> bool:
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    if "threads" not in tables:
        return False
    columns = {row[1] for row in db.execute("PRAGMA table_info(threads)")}
    return {"id", "title", "rollout_path"}.issubset(columns)


def _failed(session_id: str, message: str, title: str = "") -> RolloutReadResult:
    return RolloutReadResult("failed", session_id, message, title=display_title(title))
