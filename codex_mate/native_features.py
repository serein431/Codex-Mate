from __future__ import annotations

import shutil
import tomllib
from datetime import datetime
from pathlib import Path
import re
from typing import Any


REMOTE_FEATURE_FLAGS = (
    "local_remote_dropdown",
    "cloud_follow_up_local_remote_dropdown",
    "remote_conversation_apply_diff",
)


def default_codex_home() -> Path:
    return Path.home() / ".codex"


def config_path_for(codex_home: str | Path | None = None) -> Path:
    home = Path(codex_home).expanduser() if codex_home is not None else default_codex_home()
    return home / "config.toml"


def read_config(path: Path) -> dict[str, Any] | None:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return None
    return data if isinstance(data, dict) else None


def remote_feature_status(codex_home: str | Path | None = None) -> dict[str, object]:
    config_path = config_path_for(codex_home)
    config = read_config(config_path)
    if config is None:
        return {
            "ready": False,
            "config_path": str(config_path),
            "enabled": {},
            "required": list(REMOTE_FEATURE_FLAGS),
            "missing": list(REMOTE_FEATURE_FLAGS),
            "reason": "config_toml_missing_or_unreadable",
        }

    features = config.get("features")
    enabled = features if isinstance(features, dict) else {}
    missing = [flag for flag in REMOTE_FEATURE_FLAGS if enabled.get(flag) is not True]
    return {
        "ready": not missing,
        "config_path": str(config_path),
        "enabled": {str(key): value for key, value in enabled.items() if isinstance(key, str)},
        "required": list(REMOTE_FEATURE_FLAGS),
        "missing": missing,
        "reason": "" if not missing else "remote feature flags missing",
    }


def ensure_remote_feature_flags(codex_home: str | Path | None = None) -> dict[str, object]:
    config_path = config_path_for(codex_home)
    status = remote_feature_status(config_path.parent)
    if status["ready"]:
        return {
            "status": "skipped",
            "reason": "remote feature flags already enabled",
            "config_path": str(config_path),
            "updated_features": [],
        }
    if not config_path.exists():
        return {
            "status": "skipped",
            "reason": "config.toml not found",
            "config_path": str(config_path),
            "updated_features": [],
        }

    text = config_path.read_text(encoding="utf-8")
    updated = set_remote_feature_flags_in_toml(text)
    if updated == text:
        return {
            "status": "skipped",
            "reason": "remote feature flags already enabled",
            "config_path": str(config_path),
            "updated_features": [],
        }

    backup_path = backup_config(config_path)
    config_path.write_text(updated, encoding="utf-8")
    return {
        "status": "updated",
        "reason": "remote feature flags enabled",
        "config_path": str(config_path),
        "backup_path": str(backup_path),
        "updated_features": list(REMOTE_FEATURE_FLAGS),
    }


def backup_config(config_path: Path) -> Path:
    backup_dir = config_path.parent / "codex_mate_config_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = backup_dir / f"config.toml.native-features.{stamp}.bak"
    shutil.copy2(config_path, backup_path)
    return backup_path


def set_remote_feature_flags_in_toml(text: str) -> str:
    lines = text.splitlines(keepends=True)
    section_start = find_table_start(lines, "features")
    if section_start is None:
        suffix = "" if not text or text.endswith("\n") else "\n"
        return text + suffix + "[features]\n" + "".join(f"{flag} = true\n" for flag in REMOTE_FEATURE_FLAGS)

    section_end = find_next_table_start(lines, section_start + 1)
    existing = {flag: None for flag in REMOTE_FEATURE_FLAGS}
    for index in range(section_start + 1, section_end):
        for flag in REMOTE_FEATURE_FLAGS:
            if feature_assignment_line(lines[index], flag):
                existing[flag] = index

    for flag, index in existing.items():
        if index is not None:
            newline = "\n" if lines[index].endswith("\n") else ""
            lines[index] = f"{flag} = true{newline}"

    missing_lines = [f"{flag} = true\n" for flag, index in existing.items() if index is None]
    if missing_lines:
        if section_end > section_start + 1 and not lines[section_end - 1].endswith("\n"):
            lines[section_end - 1] += "\n"
        lines[section_end:section_end] = missing_lines
    return "".join(lines)


def find_table_start(lines: list[str], table_name: str) -> int | None:
    needle = f"[{table_name}]"
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped == needle:
            return index
    return None


def find_next_table_start(lines: list[str], start: int) -> int:
    for index in range(start, len(lines)):
        stripped = lines[index].strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            return index
    return len(lines)


def feature_assignment_line(line: str, flag: str) -> bool:
    return re.match(rf"^\s*{re.escape(flag)}\s*=", line) is not None
