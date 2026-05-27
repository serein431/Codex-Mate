from __future__ import annotations

import json
import socket
import sys
import tomllib
from pathlib import Path
from typing import Any

from codex_mate import __version__, app_paths, native_features, runtime, watcher


def port_listening(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def default_codex_home() -> Path:
    return Path.home() / ".codex"


def read_json_object(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def read_toml_object(path: Path) -> dict[str, Any] | None:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return None
    return data if isinstance(data, dict) else None


def provider_requires_openai_auth(config: dict[str, Any], provider_name: str) -> bool | None:
    if provider_name == "openai":
        return True
    providers = config.get("model_providers")
    if not isinstance(providers, dict):
        return None
    provider = providers.get(provider_name)
    if not isinstance(provider, dict):
        return None
    return provider.get("requires_openai_auth") is True


def collect_mobile_remote_status(codex_home: Path | None = None) -> dict[str, Any]:
    home = (codex_home or default_codex_home()).expanduser()
    auth_path = home / "auth.json"
    config_path = home / "config.toml"
    warnings: list[str] = []
    remote_features = native_features.remote_feature_status(home)
    for flag in remote_features.get("missing", []):
        warnings.append(f"remote_feature_{flag}_is_not_true")

    auth = read_json_object(auth_path)
    if auth is None:
        warnings.append("auth_json_missing_or_unreadable")
        auth_mode = ""
        openai_api_key_present: bool | None = None
    else:
        auth_mode = str(auth.get("auth_mode") or "")
        openai_api_key_present = bool(auth.get("OPENAI_API_KEY"))
        if auth_mode != "chatgpt":
            warnings.append("auth_mode_is_not_chatgpt")
        if openai_api_key_present:
            warnings.append("openai_api_key_is_set")

    config = read_toml_object(config_path)
    if config is None:
        warnings.append("config_toml_missing_or_unreadable")
        model_provider = ""
        requires_auth = None
    else:
        model_provider = str(config.get("model_provider") or "openai")
        requires_auth = provider_requires_openai_auth(config, model_provider)
        if requires_auth is None:
            warnings.append("model_provider_config_missing")
        elif requires_auth is not True:
            warnings.append("provider_requires_openai_auth_is_not_true")

    ready = auth_mode == "chatgpt" and openai_api_key_present is False and requires_auth is True and remote_features.get("ready") is True
    return {
        "ready": ready,
        "auth_path": str(auth_path),
        "config_path": str(config_path),
        "auth_mode": auth_mode,
        "openai_api_key_present": openai_api_key_present,
        "model_provider": model_provider,
        "provider_requires_openai_auth": requires_auth,
        "remote_feature_flags": remote_features,
        "login_preserving_provider": native_features.login_preserving_provider_status(home),
        "provider_mode": native_features.provider_mode_status(home),
        "auth_enhancement_mode": native_features.auth_enhancement_mode_status(home),
        "warnings": warnings,
    }


def collect_status() -> dict[str, Any]:
    disabled_flag = watcher.watcher_disabled_flag()
    lock_path = watcher.watcher_lock_path(9229)
    cache_path = app_paths.codex_app_dir_cache_path()
    resolved = app_paths.resolve_codex_app_dir()
    return {
        "version": __version__,
        "platform": sys.platform,
        "frozen": runtime.is_frozen(),
        "launch_mode": "direct_launcher" if disabled_flag.exists() else "watcher_available",
        "watcher": {
            "enabled": not disabled_flag.exists(),
            "disabled_flag": str(disabled_flag),
            "lock_path": str(lock_path),
            "lock_exists": lock_path.exists(),
        },
        "ports": {
            "cdp_9229": port_listening(9229),
            "helper_57321": port_listening(57321),
        },
        "codex_app": {
            "cache_path": str(cache_path),
            "cache_exists": cache_path.exists(),
            "resolved_dir": resolved.as_posix() if resolved else "",
        },
        "mobile_remote": collect_mobile_remote_status(),
    }
