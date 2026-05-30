from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any


class CcSwitchError(RuntimeError):
    pass


def default_cc_switch_home() -> Path:
    return Path.home() / ".cc-switch"


def default_db_path(cc_switch_home: str | Path | None = None) -> Path:
    home = Path(cc_switch_home).expanduser() if cc_switch_home is not None else default_cc_switch_home()
    return home / "cc-switch.db"


def default_settings_path(cc_switch_home: str | Path | None = None) -> Path:
    home = Path(cc_switch_home).expanduser() if cc_switch_home is not None else default_cc_switch_home()
    return home / "settings.json"


def list_codex_providers(db_path: str | Path | None = None, *, login_ready: bool = False) -> list[dict[str, object]]:
    path = Path(db_path).expanduser() if db_path is not None else default_db_path()
    if not path.exists():
        return []
    providers: list[dict[str, object]] = []
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, name, settings_config, is_current
            FROM providers
            WHERE app_type = 'codex'
            ORDER BY COALESCE(sort_index, 999999), created_at ASC, id ASC
            """
        ).fetchall()
    for row in rows:
        try:
            raw_config = json.loads(str(row["settings_config"] or "{}"))
        except json.JSONDecodeError:
            continue
        provider = provider_from_settings_config(
            source_id=str(row["id"]),
            name=str(row["name"]),
            settings_config=raw_config,
            is_current=bool(row["is_current"]),
            login_ready=login_ready,
        )
        if provider is not None:
            providers.append(sanitized_provider(provider))
    return providers


def get_codex_provider(db_path: str | Path | None, source_id: str, *, login_ready: bool = False) -> dict[str, object]:
    source_id = str(source_id or "").strip()
    for provider in raw_codex_providers(db_path, login_ready=login_ready):
        if provider["source_id"] == source_id:
            return provider
    raise CcSwitchError(f"provider not found: {source_id}")


def raw_codex_providers(db_path: str | Path | None = None, *, login_ready: bool = False) -> list[dict[str, object]]:
    path = Path(db_path).expanduser() if db_path is not None else default_db_path()
    if not path.exists():
        return []
    providers: list[dict[str, object]] = []
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, name, settings_config, is_current
            FROM providers
            WHERE app_type = 'codex'
            ORDER BY COALESCE(sort_index, 999999), created_at ASC, id ASC
            """
        ).fetchall()
    for row in rows:
        try:
            raw_config = json.loads(str(row["settings_config"] or "{}"))
        except json.JSONDecodeError:
            continue
        provider = provider_from_settings_config(
            source_id=str(row["id"]),
            name=str(row["name"]),
            settings_config=raw_config,
            is_current=bool(row["is_current"]),
            login_ready=login_ready,
        )
        if provider is not None:
            providers.append(provider)
    return providers


def provider_from_settings_config(
    *,
    source_id: str,
    name: str,
    settings_config: dict[str, Any],
    is_current: bool,
    login_ready: bool,
) -> dict[str, object] | None:
    config_contents = string_value(settings_config.get("config"))
    auth_contents = auth_contents_from_settings(settings_config.get("auth"))
    base_url = first_non_empty(
        string_at(settings_config, "base_url", "baseURL"),
        string_at(settings_config.get("config"), "base_url", "baseURL"),
        extract_toml_string(config_contents, "base_url"),
    )
    api_key = first_non_empty(
        json_pointer_string(settings_config, "env", "OPENAI_API_KEY"),
        json_pointer_string(settings_config, "auth", "OPENAI_API_KEY"),
        string_at(settings_config, "api_key", "apiKey"),
        string_at(settings_config.get("config"), "api_key", "apiKey"),
        extract_toml_string(config_contents, "experimental_bearer_token"),
        extract_toml_string(config_contents, "api_key"),
        extract_json_string(auth_contents, "OPENAI_API_KEY"),
    )
    wire_api = normalize_wire_api(first_non_empty(string_at(settings_config, "api_format", "apiFormat"), extract_toml_string(config_contents, "wire_api")))
    provider_name = first_non_empty(extract_toml_string(config_contents, "model_provider"), sanitize_provider_id(source_id)) or "codex-mate"
    model = first_non_empty(extract_toml_string(config_contents, "model"))
    config_present = bool(config_contents.strip())
    auth_present = bool(auth_contents.strip() and auth_contents.strip() != "{}")
    is_official = not config_present and not auth_present and not base_url and not api_key
    if is_official:
        mode = "official"
        provider_name = "openai"
    elif not base_url and not api_key:
        return None
    else:
        mode = "mixed-api" if login_ready else "pure-api"
    return {
        "source_id": source_id,
        "name": name,
        "is_current": is_current,
        "mode": mode,
        "provider": provider_name,
        "base_url": base_url,
        "api_key": api_key,
        "model": model,
        "wire_api": wire_api,
        "config_present": config_present,
        "auth_present": auth_present,
    }


def sanitized_provider(provider: dict[str, object]) -> dict[str, object]:
    return {
        "source_id": provider["source_id"],
        "name": provider["name"],
        "is_current": provider["is_current"],
        "mode": provider["mode"],
        "provider": provider["provider"],
        "base_url": provider["base_url"],
        "model": provider["model"],
        "wire_api": provider["wire_api"],
        "api_key_present": bool(provider.get("api_key")),
        "config_present": provider["config_present"],
        "auth_present": provider["auth_present"],
    }


def profile_from_provider(provider: dict[str, object]) -> dict[str, object]:
    return {
        "mode": provider["mode"],
        "provider": provider["provider"],
        "base_url": provider["base_url"],
        "api_key": provider.get("api_key", ""),
        "model": provider.get("model", ""),
        "wire_api": provider.get("wire_api", "responses"),
    }


def set_current_codex_provider(db_path: str | Path | None, settings_path: str | Path | None, source_id: str) -> bool:
    db = Path(db_path).expanduser() if db_path is not None else default_db_path()
    settings = Path(settings_path).expanduser() if settings_path is not None else default_settings_path()
    source_id = str(source_id or "").strip()
    if not source_id or not db.exists():
        return False
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE providers SET is_current = 0 WHERE app_type = 'codex'")
        cursor = conn.execute("UPDATE providers SET is_current = 1 WHERE id = ? AND app_type = 'codex'", (source_id,))
        affected = cursor.rowcount
        conn.commit()
    if affected <= 0:
        return False
    set_current_codex_provider_in_settings(settings, source_id)
    return True


def set_current_codex_provider_in_settings(path: Path, source_id: str) -> None:
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except json.JSONDecodeError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    data["currentProviderCodex"] = source_id
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def auth_contents_from_settings(value: object) -> str:
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if isinstance(value, str):
        return value
    return ""


def string_value(value: object) -> str:
    return value if isinstance(value, str) else ""


def string_at(value: object, *keys: str) -> str:
    if not isinstance(value, dict):
        return ""
    for key in keys:
        item = value.get(key)
        if isinstance(item, str) and item.strip():
            return item.strip()
    return ""


def json_pointer_string(value: object, *keys: str) -> str:
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return ""
        current = current.get(key)
    return current.strip() if isinstance(current, str) else ""


def extract_json_string(text: str, key: str) -> str:
    if not text.strip():
        return ""
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return ""
    return string_at(value, key)


def first_non_empty(*values: object) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def normalize_wire_api(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"chat", "chat_completions", "chat-completions", "openai_chat", "openai-chat"}:
        return "chat"
    return "responses"


def extract_toml_string(text: str, key: str) -> str:
    if not text:
        return ""
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=\s*(['\"])(.*?)\1\s*$")
    for line in text.splitlines():
        match = pattern.match(line)
        if match:
            return match.group(2).strip()
    return ""


def sanitize_provider_id(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_]+", "_", value.strip()).strip("_").lower()
    return sanitized or "cc-switch"
