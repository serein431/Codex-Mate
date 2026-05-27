from __future__ import annotations

import json
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
LOGIN_TOKEN_KEYS = ("access_token", "id_token", "refresh_token")
PROVIDER_MODES = ("official", "mixed-api", "pure-api")
AUTH_ENHANCEMENT_MODES = ("loginPreserving", "forceInject")
AUTH_ENHANCEMENT_MODE_ALIASES = {
    "loginpreserving": "loginPreserving",
    "login-preserving": "loginPreserving",
    "login_preserving": "loginPreserving",
    "relay": "loginPreserving",
    "mixed-api": "loginPreserving",
    "official": "loginPreserving",
    "forceinject": "forceInject",
    "force-inject": "forceInject",
    "force_inject": "forceInject",
    "patch": "forceInject",
    "pure-api": "forceInject",
}


def default_codex_home() -> Path:
    return Path.home() / ".codex"


def default_codex_mate_home() -> Path:
    return Path.home() / ".codex-mate"


def config_path_for(codex_home: str | Path | None = None) -> Path:
    home = Path(codex_home).expanduser() if codex_home is not None else default_codex_home()
    return home / "config.toml"


def settings_path_for(settings_home: str | Path | None = None) -> Path:
    home = Path(settings_home).expanduser() if settings_home is not None else default_codex_mate_home()
    return home / "settings.json"


def read_config(path: Path) -> dict[str, Any] | None:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return None
    return data if isinstance(data, dict) else None


def read_json_object(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
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

    backup_path = backup_config(config_path, "native-features")
    config_path.write_text(updated, encoding="utf-8")
    return {
        "status": "updated",
        "reason": "remote feature flags enabled",
        "config_path": str(config_path),
        "backup_path": str(backup_path),
        "updated_features": list(REMOTE_FEATURE_FLAGS),
    }


def ensure_login_preserving_provider(codex_home: str | Path | None = None) -> dict[str, object]:
    config_path = config_path_for(codex_home)
    auth_path = config_path.parent / "auth.json"
    auth = read_json_object(auth_path)
    if not chatgpt_auth_has_login_token(auth):
        return {
            "status": "skipped",
            "reason": "chatgpt login token not found",
            "config_path": str(config_path),
            "auth_path": str(auth_path),
        }

    config = read_config(config_path)
    if config is None:
        return {
            "status": "skipped",
            "reason": "config.toml missing or unreadable",
            "config_path": str(config_path),
            "auth_path": str(auth_path),
        }

    provider_name = str(config.get("model_provider") or "openai").strip() or "openai"
    if provider_name == "openai":
        return {
            "status": "skipped",
            "reason": "official provider already uses ChatGPT login",
            "config_path": str(config_path),
            "auth_path": str(auth_path),
            "provider": provider_name,
        }

    provider = provider_config(config, provider_name)
    if provider is None:
        return {
            "status": "skipped",
            "reason": "model provider config missing",
            "config_path": str(config_path),
            "auth_path": str(auth_path),
            "provider": provider_name,
        }

    api_key = first_non_empty_string(
        auth.get("OPENAI_API_KEY") if auth else None,
        config.get("OPENAI_API_KEY"),
        provider.get("experimental_bearer_token"),
        provider.get("api_key"),
    )
    base_url = first_non_empty_string(provider.get("base_url"))
    if not api_key:
        return {
            "status": "skipped",
            "reason": "provider api key not found",
            "config_path": str(config_path),
            "auth_path": str(auth_path),
            "provider": provider_name,
        }
    if not base_url:
        return {
            "status": "skipped",
            "reason": "provider base_url not found",
            "config_path": str(config_path),
            "auth_path": str(auth_path),
            "provider": provider_name,
        }

    config_text = config_path.read_text(encoding="utf-8")
    updated_config = set_login_preserving_provider_in_toml(
        config_text,
        provider_name=provider_name,
        provider_title=first_non_empty_string(provider.get("name")) or provider_name,
        base_url=base_url,
        api_key=api_key,
        wire_api=first_non_empty_string(provider.get("wire_api")) or "responses",
    )
    auth_updated = dict(auth or {})
    auth_removed_key = auth_updated.pop("OPENAI_API_KEY", None) is not None
    config_changed = updated_config != config_text
    if not config_changed and not auth_removed_key:
        return {
            "status": "skipped",
            "reason": "login-preserving provider already enabled",
            "config_path": str(config_path),
            "auth_path": str(auth_path),
            "provider": provider_name,
        }

    config_backup_path = backup_config(config_path, "login-preserving-provider") if config_changed else None
    auth_backup_path = backup_auth(auth_path) if auth_removed_key else None
    if config_changed:
        config_path.write_text(updated_config, encoding="utf-8")
    if auth_removed_key:
        auth_path.write_text(json.dumps(auth_updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "status": "updated",
        "reason": "login-preserving provider enabled",
        "config_path": str(config_path),
        "auth_path": str(auth_path),
        "provider": provider_name,
        "config_backup_path": str(config_backup_path) if config_backup_path else "",
        "auth_backup_path": str(auth_backup_path) if auth_backup_path else "",
    }


def login_preserving_provider_status(codex_home: str | Path | None = None) -> dict[str, object]:
    config_path = config_path_for(codex_home)
    auth_path = config_path.parent / "auth.json"
    auth = read_json_object(auth_path)
    config = read_config(config_path)
    provider_name = ""
    provider: dict[str, Any] | None = None
    if config is not None:
        provider_name = str(config.get("model_provider") or "openai").strip() or "openai"
        provider = provider_config(config, provider_name)
    provider_requires_auth = provider.get("requires_openai_auth") is True if provider else provider_name == "openai"
    provider_has_bearer = bool(first_non_empty_string(provider.get("experimental_bearer_token") if provider else None))
    provider_has_base_url = bool(first_non_empty_string(provider.get("base_url") if provider else None))
    auth_openai_key_present = bool(auth.get("OPENAI_API_KEY")) if auth else None
    chatgpt_login_token_present = chatgpt_auth_has_login_token(auth)
    ready = (
        provider_name != "openai"
        and chatgpt_login_token_present
        and auth_openai_key_present is False
        and provider_requires_auth
        and provider_has_bearer
        and provider_has_base_url
    )
    return {
        "ready": ready,
        "config_path": str(config_path),
        "auth_path": str(auth_path),
        "provider": provider_name,
        "chatgpt_login_token_present": chatgpt_login_token_present,
        "auth_openai_api_key_present": auth_openai_key_present,
        "provider_requires_openai_auth": provider_requires_auth,
        "provider_has_bearer_token": provider_has_bearer,
        "provider_has_base_url": provider_has_base_url,
    }


def provider_mode_status(codex_home: str | Path | None = None) -> dict[str, object]:
    config_path = config_path_for(codex_home)
    auth_path = config_path.parent / "auth.json"
    auth = read_json_object(auth_path)
    config = read_config(config_path)
    provider_name = ""
    provider: dict[str, Any] | None = None
    if config is not None:
        provider_name = str(config.get("model_provider") or "openai").strip() or "openai"
        provider = provider_config(config, provider_name)

    auth_openai_key_present = bool(auth.get("OPENAI_API_KEY")) if auth else None
    chatgpt_login_token_present = chatgpt_auth_has_login_token(auth)
    provider_requires_auth = provider.get("requires_openai_auth") is True if provider else provider_name == "openai"
    provider_has_bearer = bool(first_non_empty_string(provider.get("experimental_bearer_token") if provider else None))
    provider_has_base_url = bool(first_non_empty_string(provider.get("base_url") if provider else None))

    if auth_openai_key_present:
        mode = "pure-api"
    elif provider_name not in ("", "openai") and chatgpt_login_token_present and provider_requires_auth and provider_has_bearer and provider_has_base_url:
        mode = "mixed-api"
    elif provider_name in ("", "openai") and chatgpt_login_token_present:
        mode = "official"
    else:
        mode = "unknown"

    return {
        "mode": mode,
        "config_path": str(config_path),
        "auth_path": str(auth_path),
        "provider": provider_name,
        "chatgpt_login_token_present": chatgpt_login_token_present,
        "auth_openai_api_key_present": auth_openai_key_present,
        "provider_requires_openai_auth": provider_requires_auth,
        "provider_has_bearer_token": provider_has_bearer,
        "provider_has_base_url": provider_has_base_url,
    }


def normalize_auth_enhancement_mode(mode: object) -> str:
    raw = str(mode or "").strip()
    if raw in AUTH_ENHANCEMENT_MODES:
        return raw
    return AUTH_ENHANCEMENT_MODE_ALIASES.get(raw.lower(), "")


def default_auth_enhancement_mode_for_provider(provider_status: dict[str, object]) -> str:
    provider_mode = str(provider_status.get("mode") or "")
    return "loginPreserving" if provider_mode in ("official", "mixed-api") else "forceInject"


def auth_enhancement_flags(mode: str) -> dict[str, object]:
    force_enabled = mode == "forceInject"
    return {
        "auth_enhancement_mode": mode,
        "authEnhancementMode": mode,
        "pluginEntryUnlock": force_enabled,
        "forcePluginInstall": force_enabled,
    }


def auth_enhancement_message(mode: str, provider_status: dict[str, object], provider_action: dict[str, object] | None = None) -> str:
    login_ready = provider_status.get("chatgpt_login_token_present") is True
    if mode == "loginPreserving" and not login_ready:
        return "请先在 Codex 中登录 ChatGPT。保留登录态需要检测到官方账号登录后才能启用。"
    if mode == "forceInject":
        return "强制注入已启用：插件入口解锁和强制安装会由前端接管。"
    action_status = str((provider_action or {}).get("status") or "")
    action_reason = str((provider_action or {}).get("reason") or "")
    if action_status == "updated":
        return "保持登录态已启用：已把当前 provider 调整为保留原生登录态的配置。"
    if provider_status.get("mode") in ("official", "mixed-api"):
        return "保持登录态已启用：已关闭前端强制注入，移动端、Remote 和原生入口优先走 Codex 登录态。"
    if action_reason == "chatgpt login token not found":
        return "已关闭前端强制注入；当前未检测到 ChatGPT 登录态，请先在 Codex 登录后再切换 provider。"
    if action_reason:
        return f"已关闭前端强制注入；当前 provider 暂未自动迁移：{action_reason}。"
    return "保持登录态已启用：已关闭前端强制注入。"


def auth_enhancement_status_text(mode: str, provider_status: dict[str, object]) -> tuple[str, str]:
    login_ready = provider_status.get("chatgpt_login_token_present") is True
    provider_mode = str(provider_status.get("mode") or "unknown")
    provider = str(provider_status.get("provider") or "openai")
    if not login_ready:
        return (
            "未检测到 ChatGPT 登录",
            "请先在 Codex 中登录 ChatGPT。登录后点“我已登录，重新检测”，再启用保留登录态。",
        )
    if mode == "loginPreserving":
        return (
            "已检测到 ChatGPT 登录",
            f"推荐模式可用：当前 provider 为 {provider}（{provider_mode}），移动端、Remote 和原生入口会优先走官方登录态。",
        )
    return (
        "已检测到 ChatGPT 登录",
        "当前启用了强制注入。需要保留移动端、Remote 和原生入口时，可以切回推荐模式。",
    )


def read_codex_mate_settings(settings_home: str | Path | None = None) -> dict[str, Any]:
    settings = read_json_object(settings_path_for(settings_home))
    return dict(settings or {})


def write_codex_mate_auth_enhancement_mode(settings_home: str | Path | None, mode: str) -> bool:
    settings_path = settings_path_for(settings_home)
    settings = read_codex_mate_settings(settings_home)
    next_settings = dict(settings)
    next_settings["auth_enhancement_mode"] = mode
    if next_settings == settings:
        return False
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(next_settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


def auth_enhancement_mode_status(
    codex_home: str | Path | None = None,
    *,
    settings_home: str | Path | None = None,
) -> dict[str, object]:
    settings = read_codex_mate_settings(settings_home)
    provider_status = provider_mode_status(codex_home)
    login_preserving_available = provider_status.get("chatgpt_login_token_present") is True
    mode = normalize_auth_enhancement_mode(settings.get("auth_enhancement_mode") or settings.get("authEnhancementMode"))
    if not mode:
        mode = default_auth_enhancement_mode_for_provider(provider_status)
    if mode == "loginPreserving" and not login_preserving_available:
        mode = "forceInject"
    summary, detail = auth_enhancement_status_text(mode, provider_status)
    return {
        "status": "ok",
        "settings_path": str(settings_path_for(settings_home)),
        "provider_mode": provider_status,
        "login_preserving_available": login_preserving_available,
        "needs_chatgpt_login": not login_preserving_available,
        "recommended_mode": "loginPreserving" if login_preserving_available else "forceInject",
        "summary": summary,
        "detail": detail,
        **auth_enhancement_flags(mode),
        "message": auth_enhancement_message(mode, provider_status),
    }


def set_auth_enhancement_mode(
    codex_home: str | Path | None = None,
    *,
    settings_home: str | Path | None = None,
    mode: str,
) -> dict[str, object]:
    normalized = normalize_auth_enhancement_mode(mode)
    if not normalized:
        raise ValueError(f"unsupported auth enhancement mode: {mode}")

    before_provider = provider_mode_status(codex_home)
    if normalized == "loginPreserving" and before_provider.get("chatgpt_login_token_present") is not True:
        status = auth_enhancement_mode_status(codex_home, settings_home=settings_home)
        return {
            **status,
            "status": "failed",
            "provider_action": {"status": "skipped", "reason": "chatgpt login token not found"},
            "message": auth_enhancement_message("loginPreserving", before_provider),
        }

    provider_action: dict[str, object] = {"status": "skipped", "reason": "provider config unchanged"}
    if normalized == "loginPreserving":
        if before_provider.get("mode") in ("official", "mixed-api"):
            provider_action = {"status": "skipped", "reason": "provider already preserves login"}
        else:
            provider_action = ensure_login_preserving_provider(codex_home)

    settings_changed = write_codex_mate_auth_enhancement_mode(settings_home, normalized)
    status = auth_enhancement_mode_status(codex_home, settings_home=settings_home)
    after_provider = provider_mode_status(codex_home)
    overall_status = "updated" if settings_changed or provider_action.get("status") == "updated" else "skipped"
    return {
        **status,
        "status": overall_status,
        "provider_mode": after_provider,
        "provider_action": provider_action,
        "message": auth_enhancement_message(normalized, after_provider, provider_action),
    }


def apply_provider_mode(
    codex_home: str | Path | None = None,
    *,
    mode: str,
    provider: str = "codex-mate",
    base_url: str = "",
    api_key: str = "",
    wire_api: str = "responses",
) -> dict[str, object]:
    mode = mode.strip().lower()
    if mode not in PROVIDER_MODES:
        raise ValueError(f"unsupported provider mode: {mode}")
    if mode == "official":
        return apply_official_provider_mode(codex_home)
    provider = provider.strip()
    base_url = base_url.strip()
    api_key = api_key.strip()
    wire_api = wire_api.strip() or "responses"
    if not provider:
        raise ValueError("provider is required")
    if not base_url:
        raise ValueError("base_url is required")
    if not api_key:
        raise ValueError("api_key is required")
    if mode == "mixed-api":
        return apply_mixed_api_provider_mode(codex_home, provider=provider, base_url=base_url, api_key=api_key, wire_api=wire_api)
    return apply_pure_api_provider_mode(codex_home, provider=provider, base_url=base_url, api_key=api_key, wire_api=wire_api)


def apply_official_provider_mode(codex_home: str | Path | None = None) -> dict[str, object]:
    config_path = config_path_for(codex_home)
    auth_path = config_path.parent / "auth.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_text = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    updated_config = set_official_provider_in_toml(config_text)
    auth = read_json_object(auth_path)
    auth_updated = dict(auth or {})
    auth_removed_key = auth_updated.pop("OPENAI_API_KEY", None) is not None
    config_changed = updated_config != config_text
    if not config_changed and not auth_removed_key:
        return {
            "status": "skipped",
            "reason": "official provider mode already enabled",
            "mode": "official",
            "config_path": str(config_path),
            "auth_path": str(auth_path),
        }
    config_backup_path = backup_config(config_path, "provider-mode-official") if config_changed and config_path.exists() else None
    auth_backup_path = backup_auth(auth_path, "provider-mode-official") if auth_removed_key and auth_path.exists() else None
    if config_changed:
        config_path.write_text(updated_config, encoding="utf-8")
    if auth_removed_key:
        auth_path.write_text(json.dumps(auth_updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "status": "updated",
        "reason": "official provider mode enabled",
        "mode": "official",
        "config_path": str(config_path),
        "auth_path": str(auth_path),
        "config_backup_path": str(config_backup_path) if config_backup_path else "",
        "auth_backup_path": str(auth_backup_path) if auth_backup_path else "",
    }


def apply_mixed_api_provider_mode(
    codex_home: str | Path | None,
    *,
    provider: str,
    base_url: str,
    api_key: str,
    wire_api: str,
) -> dict[str, object]:
    config_path = config_path_for(codex_home)
    auth_path = config_path.parent / "auth.json"
    auth = read_json_object(auth_path)
    if not chatgpt_auth_has_login_token(auth):
        return {
            "status": "skipped",
            "reason": "chatgpt login token not found",
            "mode": "mixed-api",
            "config_path": str(config_path),
            "auth_path": str(auth_path),
            "provider": provider,
        }
    return apply_provider_config_with_auth_payload(
        config_path=config_path,
        auth_path=auth_path,
        mode="mixed-api",
        provider=provider,
        base_url=base_url,
        api_key=api_key,
        wire_api=wire_api,
        auth_payload=without_openai_api_key(auth),
        auth_backup_label="provider-mode-mixed-api",
    )


def apply_pure_api_provider_mode(
    codex_home: str | Path | None,
    *,
    provider: str,
    base_url: str,
    api_key: str,
    wire_api: str,
) -> dict[str, object]:
    config_path = config_path_for(codex_home)
    auth_path = config_path.parent / "auth.json"
    return apply_provider_config_with_auth_payload(
        config_path=config_path,
        auth_path=auth_path,
        mode="pure-api",
        provider=provider,
        base_url=base_url,
        api_key=api_key,
        wire_api=wire_api,
        auth_payload={"OPENAI_API_KEY": api_key},
        auth_backup_label="provider-mode-pure-api",
    )


def apply_provider_config_with_auth_payload(
    *,
    config_path: Path,
    auth_path: Path,
    mode: str,
    provider: str,
    base_url: str,
    api_key: str,
    wire_api: str,
    auth_payload: dict[str, Any],
    auth_backup_label: str,
) -> dict[str, object]:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_text = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    updated_config = set_login_preserving_provider_in_toml(
        config_text,
        provider_name=provider,
        provider_title=provider,
        base_url=base_url,
        api_key=api_key,
        wire_api=wire_api,
    )
    auth_text = auth_path.read_text(encoding="utf-8") if auth_path.exists() else ""
    updated_auth_text = json.dumps(auth_payload, ensure_ascii=False, indent=2) + "\n"
    config_changed = updated_config != config_text
    auth_changed = updated_auth_text != auth_text
    if not config_changed and not auth_changed:
        return {
            "status": "skipped",
            "reason": f"{mode} provider mode already enabled",
            "mode": mode,
            "provider": provider,
            "config_path": str(config_path),
            "auth_path": str(auth_path),
        }
    config_backup_path = backup_config(config_path, f"provider-mode-{mode}") if config_changed and config_path.exists() else None
    auth_backup_path = backup_auth(auth_path, auth_backup_label) if auth_changed and auth_path.exists() else None
    if config_changed:
        config_path.write_text(updated_config, encoding="utf-8")
    if auth_changed:
        auth_path.write_text(updated_auth_text, encoding="utf-8")
    return {
        "status": "updated",
        "reason": f"{mode} provider mode enabled",
        "mode": mode,
        "provider": provider,
        "config_path": str(config_path),
        "auth_path": str(auth_path),
        "config_backup_path": str(config_backup_path) if config_backup_path else "",
        "auth_backup_path": str(auth_backup_path) if auth_backup_path else "",
    }


def backup_config(config_path: Path, label: str = "native-features") -> Path:
    backup_dir = config_path.parent / "codex_mate_config_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = backup_dir / f"config.toml.{label}.{stamp}.bak"
    shutil.copy2(config_path, backup_path)
    return backup_path


def backup_auth(auth_path: Path, label: str = "login-preserving-provider") -> Path:
    backup_dir = auth_path.parent / "codex_mate_auth_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = backup_dir / f"auth.json.{label}.{stamp}.bak"
    shutil.copy2(auth_path, backup_path)
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


def set_login_preserving_provider_in_toml(
    text: str,
    *,
    provider_name: str,
    provider_title: str,
    base_url: str,
    api_key: str,
    wire_api: str,
) -> str:
    lines = remove_root_assignment(text.splitlines(keepends=True), "OPENAI_API_KEY")
    lines = upsert_root_assignment(lines, "model_provider", toml_string(provider_name))
    section_name = f"model_providers.{provider_name}"
    section_start = find_table_start(lines, section_name)
    if section_start is None:
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        if lines and lines[-1].strip():
            lines.append("\n")
        lines.append(f"[{section_name}]\n")
        section_start = len(lines) - 1
    section_end = find_next_table_start(lines, section_start + 1)
    assignments = {
        "name": toml_string(provider_title),
        "wire_api": toml_string(wire_api),
        "requires_openai_auth": "true",
        "base_url": toml_string(base_url),
        "experimental_bearer_token": toml_string(api_key),
    }
    return "".join(upsert_section_assignments(lines, section_start, section_end, assignments))


def set_official_provider_in_toml(text: str) -> str:
    lines = text.splitlines(keepends=True)
    lines = remove_root_assignment(lines, "OPENAI_API_KEY")
    lines = remove_root_assignment(lines, "model_provider")
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


def provider_config(config: dict[str, Any], provider_name: str) -> dict[str, Any] | None:
    providers = config.get("model_providers")
    if not isinstance(providers, dict):
        return None
    provider = providers.get(provider_name)
    return provider if isinstance(provider, dict) else None


def first_non_empty_string(*values: object) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def without_openai_api_key(auth: dict[str, Any] | None) -> dict[str, Any]:
    result = dict(auth or {})
    result.pop("OPENAI_API_KEY", None)
    return result


def chatgpt_auth_has_login_token(auth: dict[str, Any] | None) -> bool:
    if not isinstance(auth, dict):
        return False
    auth_mode = auth.get("auth_mode")
    if not isinstance(auth_mode, str) or auth_mode.lower() != "chatgpt":
        return False
    tokens = auth.get("tokens")
    if not isinstance(tokens, dict):
        return False
    return any(isinstance(tokens.get(key), str) and tokens[key].strip() for key in LOGIN_TOKEN_KEYS)


def toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def remove_root_assignment(lines: list[str], key: str) -> list[str]:
    result: list[str] = []
    in_root = True
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_root = False
        if in_root and assignment_line(line, key):
            continue
        result.append(line)
    return result


def upsert_root_assignment(lines: list[str], key: str, value: str) -> list[str]:
    root_end = find_next_table_start(lines, 0)
    for index in range(root_end):
        if assignment_line(lines[index], key):
            newline = "\n" if lines[index].endswith("\n") else ""
            lines[index] = f"{key} = {value}{newline}"
            return lines
    lines.insert(root_end, f"{key} = {value}\n")
    return lines


def upsert_section_assignments(
    lines: list[str],
    section_start: int,
    section_end: int,
    assignments: dict[str, str],
) -> list[str]:
    remaining = dict(assignments)
    for index in range(section_start + 1, section_end):
        for key, value in list(remaining.items()):
            if assignment_line(lines[index], key):
                newline = "\n" if lines[index].endswith("\n") else ""
                lines[index] = f"{key} = {value}{newline}"
                remaining.pop(key)
                break
    if remaining:
        if section_end > section_start + 1 and not lines[section_end - 1].endswith("\n"):
            lines[section_end - 1] += "\n"
        lines[section_end:section_end] = [f"{key} = {value}\n" for key, value in remaining.items()]
    return lines


def assignment_line(line: str, key: str) -> bool:
    return re.match(rf"^\s*{re.escape(key)}\s*=", line) is not None
