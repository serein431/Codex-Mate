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
PROVIDER_PROFILE_DEFAULTS = {
    "mode": "mixed-api",
    "provider": "codex-mate",
    "base_url": "",
    "api_key": "",
    "model": "",
    "wire_api": "responses",
}
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


def ensure_login_preserving_provider(
    codex_home: str | Path | None = None,
    *,
    settings_home: str | Path | None = None,
) -> dict[str, object]:
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
    saved_profile = saved_provider_profile_for(settings_home, provider_name)
    if provider is None:
        if not saved_profile:
            return {
                "status": "skipped",
                "reason": "model provider config missing",
                "config_path": str(config_path),
                "auth_path": str(auth_path),
                "provider": provider_name,
            }
        provider = {}

    api_key = first_non_empty_string(
        auth.get("OPENAI_API_KEY") if auth else None,
        config.get("OPENAI_API_KEY"),
        provider.get("experimental_bearer_token"),
        provider.get("api_key"),
        saved_profile_string(saved_profile, "api_key", "apiKey"),
    )
    base_url = first_non_empty_string(provider.get("base_url"), saved_profile_string(saved_profile, "base_url", "baseUrl"))
    if not api_key:
        return {
            "status": "skipped",
            "reason": "provider api key missing",
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
        provider_title=first_non_empty_string(provider.get("name"), saved_profile_string(saved_profile, "provider")) or provider_name,
        base_url=base_url,
        api_key=api_key,
        wire_api=first_non_empty_string(provider.get("wire_api"), saved_profile_string(saved_profile, "wire_api", "wireApi")) or "responses",
        model=first_non_empty_string(config.get("model"), saved_profile_string(saved_profile, "model")),
    )
    auth_updated = without_openai_api_key(auth)
    auth_changed = auth_updated != dict(auth or {})
    config_changed = updated_config != config_text
    if not config_changed and not auth_changed:
        return {
            "status": "skipped",
            "reason": "login-preserving provider already enabled",
            "config_path": str(config_path),
            "auth_path": str(auth_path),
            "provider": provider_name,
        }

    config_backup_path = backup_config(config_path, "login-preserving-provider") if config_changed else None
    auth_backup_path = backup_auth(auth_path) if auth_changed and auth_path.exists() else None
    if config_changed:
        config_path.write_text(updated_config, encoding="utf-8")
    if auth_changed:
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
    if action_reason == "provider api key missing":
        return "推荐模式未启用：当前 provider 缺少 API Key。请在供应商配置里填写 API Key 后点击切换供应商。"
    if action_reason == "provider base_url not found":
        return "推荐模式未启用：当前 provider 缺少 Base URL。请在供应商配置里补全 Base URL 后点击切换供应商。"
    if action_reason == "model provider config missing":
        return "推荐模式未启用：当前 provider 配置不完整。请在供应商配置里补全后点击切换供应商。"
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


def write_codex_mate_settings(settings_home: str | Path | None, settings: dict[str, Any]) -> bool:
    settings_path = settings_path_for(settings_home)
    current = read_codex_mate_settings(settings_home)
    if settings == current:
        return False
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


def write_codex_mate_auth_enhancement_mode(settings_home: str | Path | None, mode: str) -> bool:
    settings = read_codex_mate_settings(settings_home)
    next_settings = dict(settings)
    next_settings["auth_enhancement_mode"] = mode
    return write_codex_mate_settings(settings_home, next_settings)


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
            provider_action = ensure_login_preserving_provider(codex_home, settings_home=settings_home)
            if provider_action.get("status") != "updated":
                status = auth_enhancement_mode_status(codex_home, settings_home=settings_home)
                return {
                    **status,
                    "status": "failed",
                    "provider_mode": before_provider,
                    "provider_action": provider_action,
                    "message": auth_enhancement_message(normalized, before_provider, provider_action),
                }

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


def provider_profile_status(
    codex_home: str | Path | None = None,
    *,
    settings_home: str | Path | None = None,
) -> dict[str, object]:
    settings = read_codex_mate_settings(settings_home)
    profile = normalized_provider_profile(settings.get("provider_profile"), infer_provider_profile(codex_home))
    provider_status = provider_mode_status(codex_home)
    status = auth_enhancement_mode_status(codex_home, settings_home=settings_home)
    return {
        "status": "ok",
        "settings_path": str(settings_path_for(settings_home)),
        "profile": sanitized_provider_profile(profile),
        "provider_mode": provider_status,
        "auth_enhancement_mode": status["auth_enhancement_mode"],
        "recommended_mode": "loginPreserving" if profile["mode"] in ("official", "mixed-api") else "forceInject",
        "message": provider_profile_message(profile, provider_status),
    }


def apply_provider_profile(
    codex_home: str | Path | None = None,
    *,
    settings_home: str | Path | None = None,
    profile: dict[str, object],
) -> dict[str, object]:
    settings = read_codex_mate_settings(settings_home)
    previous = settings.get("provider_profile") if isinstance(settings.get("provider_profile"), dict) else infer_provider_profile(codex_home)
    normalized = normalized_provider_profile(profile, previous)
    mode = normalized["mode"]

    settings_with_profile = dict(settings)
    settings_with_profile["provider_profile"] = normalized
    write_codex_mate_settings(settings_home, settings_with_profile)

    action = apply_provider_mode(
        codex_home,
        mode=mode,
        provider=normalized["provider"],
        base_url=normalized["base_url"],
        api_key=normalized["api_key"],
        wire_api=normalized["wire_api"],
        model=normalized["model"],
    )
    action_failed = action.get("reason") == "chatgpt login token not found" or action.get("status") == "failed"
    target_auth_mode = "forceInject" if mode == "pure-api" else "loginPreserving"
    if not action_failed:
        write_codex_mate_auth_enhancement_mode(settings_home, target_auth_mode)

    status = auth_enhancement_mode_status(codex_home, settings_home=settings_home)
    provider_status = provider_mode_status(codex_home)
    overall_status = "failed" if action_failed else ("updated" if action.get("status") == "updated" else "skipped")
    message = provider_profile_apply_message(normalized, action, action_failed)
    if not action_failed and target_auth_mode == "loginPreserving" and status["auth_enhancement_mode"] != "loginPreserving":
        message = "供应商配置已保存；当前未检测到 ChatGPT 登录态，登录后可启用保留登录态。"
    return {
        **status,
        "status": overall_status,
        "profile": sanitized_provider_profile(normalized),
        "provider_action": action,
        "provider_mode": provider_status,
        "auth_enhancement_mode": status["auth_enhancement_mode"],
        "message": message,
    }


def normalized_provider_profile(profile: object, previous: object | None = None) -> dict[str, str]:
    previous_profile = previous if isinstance(previous, dict) else {}
    raw_profile = profile if isinstance(profile, dict) else {}
    merged = {**PROVIDER_PROFILE_DEFAULTS, **{str(k): v for k, v in previous_profile.items()}, **{str(k): v for k, v in raw_profile.items()}}
    mode = str(merged.get("mode") or "").strip().lower()
    if mode not in PROVIDER_MODES:
        raise ValueError(f"unsupported provider profile mode: {mode}")

    provider = str(merged.get("provider") or "").strip() or PROVIDER_PROFILE_DEFAULTS["provider"]
    base_url = str(merged.get("base_url") or merged.get("baseUrl") or "").strip()
    input_api_key = str(raw_profile.get("api_key") or raw_profile.get("apiKey") or "").strip()
    previous_api_key = str(previous_profile.get("api_key") or previous_profile.get("apiKey") or "").strip()
    api_key = input_api_key or previous_api_key
    model = str(merged.get("model") or "").strip()
    wire_api = str(merged.get("wire_api") or merged.get("wireApi") or "responses").strip().lower() or "responses"
    if wire_api not in ("responses", "chat"):
        wire_api = "responses"

    if mode != "official":
        if not provider:
            raise ValueError("provider is required")
        if not base_url:
            raise ValueError("base_url is required")
        if not api_key:
            raise ValueError("api_key is required")

    return {
        "mode": mode,
        "provider": provider,
        "base_url": base_url,
        "api_key": api_key,
        "model": model,
        "wire_api": wire_api,
    }


def sanitized_provider_profile(profile: dict[str, str]) -> dict[str, object]:
    return {
        "mode": profile["mode"],
        "provider": profile["provider"],
        "base_url": profile["base_url"],
        "model": profile["model"],
        "wire_api": profile["wire_api"],
        "api_key_present": bool(profile["api_key"]),
    }


def infer_provider_profile(codex_home: str | Path | None = None) -> dict[str, str]:
    config_path = config_path_for(codex_home)
    auth_path = config_path.parent / "auth.json"
    config = read_config(config_path) or {}
    auth = read_json_object(auth_path) or {}
    provider_status = provider_mode_status(codex_home)
    mode = str(provider_status.get("mode") or "")
    if mode not in PROVIDER_MODES:
        mode = "mixed-api" if provider_status.get("chatgpt_login_token_present") else "pure-api"
    provider_name = str(config.get("model_provider") or provider_status.get("provider") or "").strip()
    if not provider_name or provider_name == "openai":
        provider_name = PROVIDER_PROFILE_DEFAULTS["provider"]
    provider = provider_config(config, provider_name) or {}
    return {
        "mode": mode,
        "provider": provider_name,
        "base_url": first_non_empty_string(provider.get("base_url")),
        "api_key": first_non_empty_string(
            provider.get("experimental_bearer_token"),
            provider.get("api_key"),
            auth.get("OPENAI_API_KEY"),
            config.get("OPENAI_API_KEY"),
        ),
        "model": first_non_empty_string(config.get("model")),
        "wire_api": first_non_empty_string(provider.get("wire_api")) or "responses",
    }


def provider_profile_message(profile: dict[str, str], provider_status: dict[str, object]) -> str:
    mode = profile["mode"]
    if mode == "official":
        return "官方登录模式会保留 Codex 原生登录态，不写入 API Key。"
    if mode == "mixed-api":
        if provider_status.get("chatgpt_login_token_present") is not True:
            return "保留登录态 + API 需要先在 Codex 中登录 ChatGPT。"
        return "保留登录态 + API 会写入 provider 配置，并保留移动端、Remote 和原生入口。"
    return "纯 API 会写入 config.toml 和 auth.json，并启用完整增强。"


def provider_profile_apply_message(profile: dict[str, str], action: dict[str, object], failed: bool) -> str:
    if failed:
        reason = str(action.get("reason") or "provider profile apply failed")
        if reason == "chatgpt login token not found":
            return "当前未检测到 ChatGPT 登录态；请先登录后再使用保留登录态 + API。"
        return f"供应商切换失败：{reason}。"
    if profile["mode"] == "official":
        return "已切回官方登录模式；页面增强已设为保留登录态。"
    if profile["mode"] == "mixed-api":
        return "已切换到保留登录态 + API；页面增强已设为保留登录态。"
    return "已切换到纯 API；页面增强已设为强制注入。"


def apply_provider_mode(
    codex_home: str | Path | None = None,
    *,
    mode: str,
    provider: str = "codex-mate",
    base_url: str = "",
    api_key: str = "",
    wire_api: str = "responses",
    model: str = "",
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
        return apply_mixed_api_provider_mode(codex_home, provider=provider, base_url=base_url, api_key=api_key, wire_api=wire_api, model=model)
    return apply_pure_api_provider_mode(codex_home, provider=provider, base_url=base_url, api_key=api_key, wire_api=wire_api, model=model)


def apply_official_provider_mode(codex_home: str | Path | None = None) -> dict[str, object]:
    config_path = config_path_for(codex_home)
    auth_path = config_path.parent / "auth.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_text = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    updated_config = set_official_provider_in_toml(config_text)
    auth = read_json_object(auth_path)
    auth_updated = without_openai_api_key(auth)
    auth_changed = auth_updated != dict(auth or {})
    config_changed = updated_config != config_text
    if not config_changed and not auth_changed:
        return {
            "status": "skipped",
            "reason": "official provider mode already enabled",
            "mode": "official",
            "config_path": str(config_path),
            "auth_path": str(auth_path),
        }
    config_backup_path = backup_config(config_path, "provider-mode-official") if config_changed and config_path.exists() else None
    auth_backup_path = backup_auth(auth_path, "provider-mode-official") if auth_changed and auth_path.exists() else None
    if config_changed:
        config_path.write_text(updated_config, encoding="utf-8")
    if auth_changed:
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
    model: str = "",
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
        model=model,
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
    model: str = "",
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
        model=model,
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
    model: str = "",
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
        model=model,
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
    model: str = "",
) -> str:
    lines = remove_root_assignment(text.splitlines(keepends=True), "OPENAI_API_KEY")
    lines = upsert_root_assignment(lines, "model_provider", toml_string(provider_name))
    if model.strip():
        lines = upsert_root_assignment(lines, "model", toml_string(model.strip()))
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


def saved_provider_profile_for(settings_home: str | Path | None, provider_name: str) -> dict[str, Any]:
    settings = read_codex_mate_settings(settings_home)
    profile = settings.get("provider_profile")
    if not isinstance(profile, dict):
        return {}
    saved_provider = first_non_empty_string(profile.get("provider"))
    if saved_provider and saved_provider != provider_name:
        return {}
    return dict(profile)


def saved_profile_string(profile: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = profile.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def without_openai_api_key(auth: dict[str, Any] | None) -> dict[str, Any]:
    result = dict(auth or {})
    result.pop("OPENAI_API_KEY", None)
    if auth_tokens_have_login_secret(result.get("tokens")):
        result["auth_mode"] = "chatgpt"
    return result


def auth_tokens_have_login_secret(tokens: object) -> bool:
    if not isinstance(tokens, dict):
        return False
    return any(isinstance(tokens.get(key), str) and tokens[key].strip() for key in LOGIN_TOKEN_KEYS)


def chatgpt_auth_has_login_token(auth: dict[str, Any] | None) -> bool:
    if not isinstance(auth, dict):
        return False
    return auth_tokens_have_login_secret(auth.get("tokens"))


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
