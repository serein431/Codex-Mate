from __future__ import annotations

import json
import os
import shutil
import tomllib
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any

from codex_mate import cc_switch, history_sync


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
CURATED_PLUGIN_SOURCE_MARKETPLACE_NAME = "openai-curated"
CURATED_PLUGIN_MARKETPLACE_NAME = "openai-curated"
CURATED_PLUGIN_MANAGED_ALIAS_MARKETPLACE_NAME = "openai-bundled"
LEGACY_CURATED_PLUGIN_MARKETPLACE_NAMES = ("openai-curated", "openai-curated-remote")


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


def codex_resources_dir(app_dir: str | Path | None) -> Path | None:
    if app_dir is None:
        return None
    root = Path(app_dir).expanduser()
    candidates = [
        root / "Contents" / "Resources",
        root / "resources",
        root / "Resources",
        root,
    ]
    return next((path for path in candidates if (path / "plugins" / "openai-bundled" / ".agents" / "plugins" / "marketplace.json").exists()), None)


def bundled_plugin_marketplace_path(root: Path) -> Path:
    return root / ".agents" / "plugins" / "marketplace.json"


def bundled_plugin_signature(marketplace_root: Path) -> dict[str, str]:
    manifest = read_json_object(bundled_plugin_marketplace_path(marketplace_root)) or {}
    plugins = manifest.get("plugins")
    signature: dict[str, str] = {}
    if not isinstance(plugins, list):
        return signature
    for item in plugins:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        plugin_json = marketplace_root / "plugins" / name / ".codex-plugin" / "plugin.json"
        plugin_manifest = read_json_object(plugin_json) or {}
        version = str(plugin_manifest.get("version") or "")
        signature[name] = version
    return dict(sorted(signature.items()))


def bundled_plugin_cache_path(codex_home: str | Path | None = None, marketplace_name: str = "openai-bundled") -> Path:
    home = Path(codex_home).expanduser() if codex_home is not None else default_codex_home()
    return home / ".tmp" / "bundled-marketplaces" / marketplace_name


def curated_plugin_marketplace_root(codex_home: str | Path | None = None) -> Path:
    home = Path(codex_home).expanduser() if codex_home is not None else default_codex_home()
    return home / ".tmp" / "plugins"


def curated_plugin_marketplace_alias_root(
    codex_home: str | Path | None = None,
    *,
    marketplace_name: str = CURATED_PLUGIN_MARKETPLACE_NAME,
) -> Path:
    home = Path(codex_home).expanduser() if codex_home is not None else default_codex_home()
    return home / ".tmp" / "codex-mate-marketplaces" / marketplace_name


def curated_plugin_marketplace_path(marketplace_root: Path) -> Path:
    return marketplace_root / ".agents" / "plugins" / "marketplace.json"


def curated_plugin_alias_manifest(source_root: Path, alias_root: Path, marketplace_name: str) -> dict[str, Any] | None:
    source_manifest = read_json_object(curated_plugin_marketplace_path(source_root))
    if not isinstance(source_manifest, dict):
        return None
    plugins = source_manifest.get("plugins")
    if not isinstance(plugins, list):
        return None

    alias_plugins: list[object] = []
    for item in plugins:
        if not isinstance(item, dict):
            alias_plugins.append(item)
            continue
        source = item.get("source")
        if not isinstance(source, dict):
            alias_plugins.append(item)
            continue
        rel_path = source.get("path")
        if not isinstance(rel_path, str) or not rel_path.strip():
            alias_plugins.append(item)
            continue
        plugin_root = (source_root / rel_path).resolve()
        alias_path = os.path.relpath(plugin_root, alias_root).replace("\\", "/")
        if not alias_path.startswith("."):
            alias_path = f"./{alias_path}"
        alias_plugins.append({**item, "source": {**source, "path": alias_path}})

    source_interface = source_manifest.get("interface")
    interface = dict(source_interface) if isinstance(source_interface, dict) else {}
    interface.setdefault("version", 1)
    interface["displayName"] = "OpenAI Bundled"
    return {
        **source_manifest,
        "name": marketplace_name,
        "interface": interface,
        "plugins": alias_plugins,
    }


def curated_plugin_marketplace_alias_status(
    codex_home: str | Path | None = None,
    *,
    marketplace_name: str = CURATED_PLUGIN_MARKETPLACE_NAME,
) -> dict[str, object]:
    source_root = curated_plugin_marketplace_root(codex_home)
    alias_root = curated_plugin_marketplace_alias_root(codex_home, marketplace_name=marketplace_name)
    alias_manifest_path = curated_plugin_marketplace_path(alias_root)
    expected = curated_plugin_alias_manifest(source_root, alias_root, marketplace_name)
    current = read_json_object(alias_manifest_path)
    ready = expected is not None and current == expected
    return {
        "ready": ready,
        "source_path": str(source_root),
        "alias_path": str(alias_root),
        "alias_manifest_path": str(alias_manifest_path),
        "reason": "curated plugin marketplace alias is current" if ready else "curated plugin marketplace alias missing or stale",
    }


def ensure_curated_plugin_marketplace_alias(
    codex_home: str | Path | None = None,
    *,
    marketplace_name: str = CURATED_PLUGIN_MARKETPLACE_NAME,
) -> dict[str, object]:
    source_root = curated_plugin_marketplace_root(codex_home)
    alias_root = curated_plugin_marketplace_alias_root(codex_home, marketplace_name=marketplace_name)
    alias_manifest_path = curated_plugin_marketplace_path(alias_root)
    expected = curated_plugin_alias_manifest(source_root, alias_root, marketplace_name)
    if expected is None:
        status = curated_plugin_marketplace_alias_status(codex_home, marketplace_name=marketplace_name)
        return {"status": "skipped", **status}
    current = read_json_object(alias_manifest_path)
    if current == expected:
        status = curated_plugin_marketplace_alias_status(codex_home, marketplace_name=marketplace_name)
        return {"status": "skipped", **status}
    alias_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    alias_manifest_path.write_text(json.dumps(expected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    status = curated_plugin_marketplace_alias_status(codex_home, marketplace_name=marketplace_name)
    return {"status": "updated", **status}


def curated_plugin_marketplace_status(
    codex_home: str | Path | None = None,
    *,
    marketplace_name: str = CURATED_PLUGIN_MARKETPLACE_NAME,
) -> dict[str, object]:
    root = curated_plugin_marketplace_root(codex_home)
    manifest_path = curated_plugin_marketplace_path(root)
    config_path = config_path_for(codex_home)
    manifest = read_json_object(manifest_path)
    plugins = manifest.get("plugins") if isinstance(manifest, dict) else None
    plugin_count = len(plugins) if isinstance(plugins, list) else 0
    invalid_plugins = curated_marketplace_invalid_plugins(root, plugins if isinstance(plugins, list) else [])
    config = read_config(config_path)
    marketplace_config = marketplace_config_for(config, marketplace_name)
    registered = marketplace_config_source_matches(marketplace_config, root)
    managed_alias_path = curated_plugin_marketplace_alias_root(
        codex_home,
        marketplace_name=CURATED_PLUGIN_MANAGED_ALIAS_MARKETPLACE_NAME,
    )
    managed_alias_config = marketplace_config_for(config, CURATED_PLUGIN_MANAGED_ALIAS_MARKETPLACE_NAME)
    managed_alias_registered = marketplace_config_source_matches(managed_alias_config, managed_alias_path)
    source_present = (
        isinstance(manifest, dict)
        and isinstance(manifest.get("name"), str)
        and isinstance(plugins, list)
        and plugin_count > 0
        and not invalid_plugins
    )
    reasons: list[str] = []
    if manifest is None:
        reasons.append("curated plugin marketplace not found")
    elif not isinstance(plugins, list) or plugin_count == 0:
        reasons.append("curated plugin marketplace has no plugins")
    if invalid_plugins:
        reasons.append("curated plugin marketplace contains invalid plugin paths")
    if config is None:
        reasons.append("config.toml missing or unreadable")
    elif not registered:
        reasons.append("curated plugin marketplace not registered in config.toml")
    if managed_alias_registered:
        reasons.append("managed bundled marketplace alias should be removed")
    ready = source_present and registered and not managed_alias_registered
    return {
        "ready": ready,
        "reason": "curated plugin marketplace is registered" if ready else "; ".join(reasons),
        "marketplace_name": marketplace_name,
        "source_ready": source_present,
        "source_path": str(root),
        "alias_ready": False,
        "alias_path": "",
        "alias_manifest_path": "",
        "manifest_path": str(manifest_path),
        "config_path": str(config_path),
        "plugin_count": plugin_count,
        "invalid_plugins": invalid_plugins,
        "registered": registered,
        "managed_alias_registered": managed_alias_registered,
    }


def ensure_curated_plugin_marketplace_registered(
    codex_home: str | Path | None = None,
    *,
    marketplace_name: str = CURATED_PLUGIN_MARKETPLACE_NAME,
) -> dict[str, object]:
    status = curated_plugin_marketplace_status(codex_home, marketplace_name=marketplace_name)
    if status.get("ready") is True:
        return {"status": "skipped", **status}
    if status.get("source_ready") is not True:
        return {"status": "skipped", **status}
    config_path = Path(str(status["config_path"]))
    if not config_path.exists() or read_config(config_path) is None:
        return {"status": "skipped", **status}
    text = config_path.read_text(encoding="utf-8")
    updated = set_local_marketplace_in_toml(
        text,
        marketplace_name=marketplace_name,
        source_path=str(status["source_path"]),
    )
    config = read_config(config_path)
    if isinstance(config, dict):
        for legacy_name in LEGACY_CURATED_PLUGIN_MARKETPLACE_NAMES:
            if legacy_name == marketplace_name:
                continue
            legacy_config = marketplace_config_for(config, legacy_name)
            if marketplace_config_source_matches(legacy_config, Path(str(status["source_path"]))):
                updated = remove_toml_table(updated, f"marketplaces.{legacy_name}")
        managed_alias_config = marketplace_config_for(config, CURATED_PLUGIN_MANAGED_ALIAS_MARKETPLACE_NAME)
        managed_alias_path = curated_plugin_marketplace_alias_root(
            codex_home,
            marketplace_name=CURATED_PLUGIN_MANAGED_ALIAS_MARKETPLACE_NAME,
        )
        if marketplace_config_source_matches(managed_alias_config, managed_alias_path):
            updated = remove_toml_table(updated, f"marketplaces.{CURATED_PLUGIN_MANAGED_ALIAS_MARKETPLACE_NAME}")
    if updated == text:
        refreshed = curated_plugin_marketplace_status(codex_home, marketplace_name=marketplace_name)
        return {"status": "skipped", **refreshed}
    backup_path = backup_config(config_path, f"marketplace-{marketplace_name}")
    config_path.write_text(updated, encoding="utf-8")
    refreshed = curated_plugin_marketplace_status(codex_home, marketplace_name=marketplace_name)
    return {
        "status": "updated",
        "backup_path": str(backup_path),
        **refreshed,
    }


def curated_marketplace_invalid_plugins(marketplace_root: Path, plugins: list[object]) -> list[str]:
    invalid: list[str] = []
    for item in plugins:
        if not isinstance(item, dict):
            invalid.append("<invalid>")
            continue
        name = str(item.get("name") or "").strip()
        source = item.get("source")
        rel_path = source.get("path") if isinstance(source, dict) else None
        if not name or not isinstance(rel_path, str) or not rel_path.strip():
            invalid.append(name or "<unnamed>")
            continue
        plugin_json = marketplace_root / rel_path / ".codex-plugin" / "plugin.json"
        if not plugin_json.exists():
            invalid.append(name)
    return invalid


def marketplace_config_for(config: dict[str, Any] | None, marketplace_name: str) -> dict[str, Any] | None:
    if not isinstance(config, dict):
        return None
    marketplaces = config.get("marketplaces")
    if not isinstance(marketplaces, dict):
        return None
    marketplace = marketplaces.get(marketplace_name)
    return marketplace if isinstance(marketplace, dict) else None


def marketplace_config_source_matches(marketplace: dict[str, Any] | None, source_root: Path) -> bool:
    if not isinstance(marketplace, dict):
        return False
    source = marketplace.get("source")
    if marketplace.get("source_type") != "local" or not isinstance(source, str):
        return False
    try:
        return Path(source).expanduser() == source_root.expanduser()
    except (OSError, RuntimeError):
        return False


def bundled_plugin_marketplace_cache_status(
    codex_home: str | Path | None = None,
    *,
    app_dir: str | Path | None = None,
    marketplace_name: str = "openai-bundled",
) -> dict[str, object]:
    resources_dir = codex_resources_dir(app_dir)
    if resources_dir is None:
        return {
            "ready": False,
            "reason": "codex bundled plugin marketplace not found",
            "source_path": "",
            "cache_path": str(bundled_plugin_cache_path(codex_home, marketplace_name)),
            "source_plugins": {},
            "cache_plugins": {},
            "missing_plugins": [],
        }
    source_root = resources_dir / "plugins" / marketplace_name
    cache_root = bundled_plugin_cache_path(codex_home, marketplace_name)
    source_signature = bundled_plugin_signature(source_root)
    cache_signature = bundled_plugin_signature(cache_root)
    missing_plugins = sorted(name for name in source_signature if name not in cache_signature)
    changed_plugins = sorted(
        name
        for name, version in source_signature.items()
        if cache_signature.get(name) not in (version, None)
    )
    return {
        "ready": source_signature == cache_signature,
        "reason": "bundled plugin cache is current" if source_signature == cache_signature else "bundled plugin cache differs from Codex app",
        "source_path": str(source_root),
        "cache_path": str(cache_root),
        "source_plugins": source_signature,
        "cache_plugins": cache_signature,
        "missing_plugins": missing_plugins,
        "changed_plugins": changed_plugins,
    }


def ensure_bundled_plugin_marketplace_cache(
    codex_home: str | Path | None = None,
    *,
    app_dir: str | Path | None = None,
    marketplace_name: str = "openai-bundled",
) -> dict[str, object]:
    status = bundled_plugin_marketplace_cache_status(codex_home, app_dir=app_dir, marketplace_name=marketplace_name)
    if not status.get("source_path"):
        return {"status": "skipped", **status}
    if status.get("ready") is True:
        return {"status": "skipped", **status}
    source_root = Path(str(status["source_path"]))
    cache_root = Path(str(status["cache_path"]))
    staging_root = cache_root.with_name(f"{cache_root.name}.staging")
    cache_root.parent.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(staging_root, ignore_errors=True)
    shutil.copytree(source_root, staging_root)
    if cache_root.exists():
        shutil.rmtree(cache_root)
    staging_root.rename(cache_root)
    updated = bundled_plugin_marketplace_cache_status(codex_home, app_dir=app_dir, marketplace_name=marketplace_name)
    return {"status": "updated", **updated}


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
    login_ready = chatgpt_auth_has_login_token(auth)

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
    config_changed = updated_config != config_text
    if not config_changed:
        return {
            "status": "skipped",
            "reason": "login-preserving provider already enabled"
            if login_ready
            else "login-preserving provider prepared; waiting for ChatGPT login",
            "config_path": str(config_path),
            "auth_path": str(auth_path),
            "provider": provider_name,
        }

    config_backup_path = backup_config(config_path, "login-preserving-provider") if config_changed else None
    if config_changed:
        config_path.write_text(updated_config, encoding="utf-8")
    return {
        "status": "updated",
        "reason": "login-preserving provider enabled" if login_ready else "login-preserving provider prepared; waiting for ChatGPT login",
        "config_path": str(config_path),
        "auth_path": str(auth_path),
        "provider": provider_name,
        "config_backup_path": str(config_backup_path) if config_backup_path else "",
        "auth_backup_path": "",
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


def login_preserving_preparation_status(
    codex_home: str | Path | None = None,
    *,
    settings_home: str | Path | None = None,
) -> dict[str, object]:
    config_path = config_path_for(codex_home)
    auth_path = config_path.parent / "auth.json"
    auth = read_json_object(auth_path)
    config = read_config(config_path)
    provider_name = ""
    provider: dict[str, Any] | None = None
    if config is not None:
        provider_name = str(config.get("model_provider") or "openai").strip() or "openai"
        provider = provider_config(config, provider_name)
    saved_profile = saved_provider_profile_for(settings_home, provider_name)
    api_key = first_non_empty_string(
        auth.get("OPENAI_API_KEY") if auth else None,
        config.get("OPENAI_API_KEY") if config else None,
        provider.get("experimental_bearer_token") if provider else None,
        provider.get("api_key") if provider else None,
        saved_profile_string(saved_profile, "api_key", "apiKey"),
    )
    base_url = first_non_empty_string(
        provider.get("base_url") if provider else None,
        saved_profile_string(saved_profile, "base_url", "baseUrl"),
    )
    provider_requires_auth = provider.get("requires_openai_auth") is True if provider else provider_name == "openai"
    provider_has_bearer = bool(first_non_empty_string(provider.get("experimental_bearer_token") if provider else None))
    provider_has_base_url = bool(first_non_empty_string(provider.get("base_url") if provider else None))
    provider_api_ready = provider_name not in ("", "openai") and bool(api_key) and bool(base_url)
    provider_config_ready = (
        provider_name not in ("", "openai")
        and provider_requires_auth
        and provider_has_bearer
        and provider_has_base_url
    )
    missing: list[str] = []
    if provider_name in ("", "openai"):
        missing.append("provider")
    if not base_url:
        missing.append("base_url")
    if not api_key:
        missing.append("api_key")
    return {
        "ready": provider_api_ready,
        "provider_config_ready": provider_config_ready,
        "provider": provider_name,
        "api_key_present": bool(api_key),
        "base_url_present": bool(base_url),
        "provider_requires_openai_auth": provider_requires_auth,
        "provider_has_bearer_token": provider_has_bearer,
        "provider_has_base_url": provider_has_base_url,
        "missing": missing,
        "config_path": str(config_path),
        "auth_path": str(auth_path),
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


def auth_enhancement_message(
    mode: str,
    provider_status: dict[str, object],
    provider_action: dict[str, object] | None = None,
    *,
    preparation_status: dict[str, object] | None = None,
    desired_mode: str | None = None,
) -> str:
    login_ready = provider_status.get("chatgpt_login_token_present") is True
    provider_ready = (preparation_status or {}).get("ready") is True
    auth_api_key_present = provider_status.get("auth_openai_api_key_present") is True
    if desired_mode == "loginPreserving" and not login_ready:
        if provider_ready:
            return "第三方 API Key 已保存到 provider。现在登录 ChatGPT，登录后点“重新检测”即可启用官方登录态保护。"
        return "请先在供应商配置或 CC Switch 中保存第三方 API Key，再登录 ChatGPT。"
    if desired_mode == "loginPreserving" and auth_api_key_present:
        return "第三方 API Key 已保存到 provider；auth.json 中仍有 OPENAI_API_KEY，登录 ChatGPT 覆盖后可启用官方登录态保护。"
    if mode == "forceInject":
        return "兼容模式已启用：Codex Mate 会用前端注入补齐插件入口，不会保护移动端或 Remote 登录态。"
    action_status = str((provider_action or {}).get("status") or "")
    action_reason = str((provider_action or {}).get("reason") or "")
    if action_status == "updated":
        if login_ready:
            return "官方登录态保护已开启：第三方 API Key 已写入 provider，auth.json 会继续保留 ChatGPT 登录。"
        return "第三方 API Key 已先写入 provider。请现在登录 ChatGPT，避免登录时覆盖掉 API Key。"
    if provider_status.get("mode") in ("official", "mixed-api"):
        return "官方登录态保护已开启：移动端、Remote 和原生入口会优先使用 ChatGPT 登录。"
    if action_reason == "chatgpt login token not found":
        return "未检测到 ChatGPT 登录。请先确认第三方 API Key 已保存到 provider，再去 Codex 登录账号。"
    if action_reason == "provider api key missing":
        return "还不能准备官方登录态保护：当前 provider 缺少 API Key。请先在供应商配置里填写 API Key。"
    if action_reason == "provider base_url not found":
        return "还不能准备官方登录态保护：当前 provider 缺少 Base URL。请先在供应商配置里补全 Base URL。"
    if action_reason == "model provider config missing":
        return "还不能准备官方登录态保护：当前 provider 配置不完整。请先补全供应商配置。"
    if action_reason:
        return f"暂未开启官方登录态保护：当前 provider 无法自动迁移，原因是 {action_reason}。"
    return "官方登录态保护已开启：已关闭前端强制注入。"


def auth_enhancement_status_text(
    mode: str,
    provider_status: dict[str, object],
    *,
    preparation_status: dict[str, object] | None = None,
    desired_mode: str | None = None,
) -> tuple[str, str]:
    login_ready = provider_status.get("chatgpt_login_token_present") is True
    provider_mode = str(provider_status.get("mode") or "unknown")
    provider = str(provider_status.get("provider") or "openai")
    if not login_ready:
        if (preparation_status or {}).get("ready") is True:
            return (
                "API Key 已保存，等待 ChatGPT 登录"
                if desired_mode == "loginPreserving"
                else "API Key 已保存，当前为兼容模式",
                "第三方 API Key 已放进 provider；现在去 Codex 登录 ChatGPT，登录完成后重新检测即可启用移动端、Remote 和原生入口。"
                if desired_mode == "loginPreserving"
                else "如需移动端、Remote 和原生入口，请切到“保护官方登录”后再登录 ChatGPT。",
            )
        return (
            "先保存第三方 API Key",
            "ChatGPT 登录会覆盖 auth.json 里的 API Key。请先把 API Key 写入 provider，再登录 ChatGPT。",
        )
    if desired_mode == "loginPreserving" and provider_status.get("auth_openai_api_key_present") is True:
        return (
            "API Key 已保存，等待官方登录覆盖 auth.json",
            "第三方 API Key 已放进 provider；auth.json 中仍有 OPENAI_API_KEY，登录 ChatGPT 覆盖后即可启用移动端、Remote 和原生入口。",
        )
    if mode == "loginPreserving":
        return (
            "官方登录态保护已开启",
            f"当前 provider 为 {provider}（{provider_mode}）。ChatGPT 登录保留在 auth.json，第三方 API Key 写入 provider。",
        )
    return (
        "已检测到 ChatGPT 登录",
        "可以开启官方登录态保护：保留移动端、Remote 和原生入口，同时让模型请求走第三方 API。",
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
    preparation_status = login_preserving_preparation_status(codex_home, settings_home=settings_home)
    login_ready = provider_status.get("chatgpt_login_token_present") is True
    provider_mode = str(provider_status.get("mode") or "")
    login_preserving_ready = login_ready and provider_mode in ("official", "mixed-api")
    desired_mode = normalize_auth_enhancement_mode(settings.get("auth_enhancement_mode") or settings.get("authEnhancementMode"))
    if not desired_mode:
        desired_mode = default_auth_enhancement_mode_for_provider(provider_status)
        if preparation_status.get("ready") is True:
            desired_mode = "loginPreserving"
    mode = desired_mode
    if mode == "loginPreserving" and not login_preserving_ready:
        mode = "forceInject"
    summary, detail = auth_enhancement_status_text(
        mode,
        provider_status,
        preparation_status=preparation_status,
        desired_mode=desired_mode,
    )
    return {
        "status": "ok",
        "settings_path": str(settings_path_for(settings_home)),
        "provider_mode": provider_status,
        "login_preserving_provider": preparation_status,
        "provider_api_ready": preparation_status.get("ready") is True,
        "provider_config_ready": preparation_status.get("provider_config_ready") is True,
        "chatgpt_login_ready": login_ready,
        "login_preserving_available": login_preserving_ready,
        "needs_chatgpt_login": not login_ready,
        "desired_auth_enhancement_mode": desired_mode,
        "recommended_mode": "loginPreserving" if login_ready or preparation_status.get("ready") is True else "forceInject",
        "summary": summary,
        "detail": detail,
        **auth_enhancement_flags(mode),
        "message": auth_enhancement_message(
            mode,
            provider_status,
            preparation_status=preparation_status,
            desired_mode=desired_mode,
        ),
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
    provider_action: dict[str, object] = {"status": "skipped", "reason": "provider config unchanged"}
    if normalized == "loginPreserving":
        if before_provider.get("mode") in ("official", "mixed-api"):
            provider_action = {"status": "skipped", "reason": "provider already preserves login"}
        else:
            provider_action = ensure_login_preserving_provider(codex_home, settings_home=settings_home)
            acceptable_reasons = {
                "login-preserving provider already enabled",
                "login-preserving provider prepared; waiting for ChatGPT login",
                "official provider already uses ChatGPT login",
            }
            if provider_action.get("status") != "updated" and provider_action.get("reason") not in acceptable_reasons:
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
        "message": auth_enhancement_message(
            status["auth_enhancement_mode"],
            after_provider,
            provider_action,
            preparation_status=status.get("login_preserving_provider") if isinstance(status.get("login_preserving_provider"), dict) else None,
            desired_mode=normalized,
        ),
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
        if provider_status.get("auth_openai_api_key_present") is True:
            message = "供应商配置已保存；auth.json 中仍有 OPENAI_API_KEY，登录 ChatGPT 覆盖后可启用保留登录态。"
        else:
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


def cc_switch_providers_status(
    codex_home: str | Path | None = None,
    *,
    cc_switch_home: str | Path | None = None,
) -> dict[str, object]:
    db_path = cc_switch.default_db_path(cc_switch_home)
    settings_path = cc_switch.default_settings_path(cc_switch_home)
    login_ready = provider_mode_status(codex_home).get("chatgpt_login_token_present") is True
    try:
        providers = cc_switch.list_codex_providers(db_path, login_ready=login_ready)
    except Exception as exc:
        return {
            "status": "failed",
            "message": f"读取 CC Switch 供应商失败：{exc}",
            "db_path": str(db_path),
            "settings_path": str(settings_path),
            "providers": [],
        }
    if not db_path.exists():
        message = "未找到 CC Switch 数据库。"
    elif not providers:
        message = "没有可用的 CC Switch Codex 供应商。"
    else:
        message = f"已读取 CC Switch Codex 供应商：{len(providers)} 个。"
    return {
        "status": "ok",
        "message": message,
        "db_path": str(db_path),
        "settings_path": str(settings_path),
        "providers": providers,
    }


def apply_cc_switch_provider(
    codex_home: str | Path | None = None,
    *,
    settings_home: str | Path | None = None,
    cc_switch_home: str | Path | None = None,
    source_id: str,
) -> dict[str, object]:
    db_path = cc_switch.default_db_path(cc_switch_home)
    settings_path = cc_switch.default_settings_path(cc_switch_home)
    login_ready = provider_mode_status(codex_home).get("chatgpt_login_token_present") is True
    try:
        provider = cc_switch.get_codex_provider(db_path, source_id, login_ready=login_ready)
    except Exception as exc:
        return {
            "status": "failed",
            "message": f"CC Switch 供应商读取失败：{exc}",
            "source_id": source_id,
            "db_path": str(db_path),
            "settings_path": str(settings_path),
        }

    profile = cc_switch.profile_from_provider(provider)
    try:
        result = apply_provider_profile(codex_home, settings_home=settings_home, profile=profile)
    except Exception as exc:
        return {
            "status": "failed",
            "message": f"CC Switch 供应商切换失败：{exc}",
            "source_id": source_id,
            "cc_switch_provider": cc_switch.sanitized_provider(provider),
            "db_path": str(db_path),
            "settings_path": str(settings_path),
        }
    if result.get("status") == "failed":
        return {
            **result,
            "source_id": source_id,
            "cc_switch_provider": cc_switch.sanitized_provider(provider),
            "db_path": str(db_path),
            "settings_path": str(settings_path),
        }

    try:
        cc_switch_changed = cc_switch.set_current_codex_provider(db_path, settings_path, source_id)
    except Exception as exc:
        return {
            **result,
            "status": "failed",
            "source_id": source_id,
            "cc_switch_provider": cc_switch.sanitized_provider(provider),
            "message": f"Codex 已切换，但同步 CC Switch 当前供应商失败：{exc}",
            "db_path": str(db_path),
            "settings_path": str(settings_path),
        }

    try:
        history_result = history_sync.sync_history_if_ready(history_sync.resolve_paths(codex_home))
    except Exception as exc:
        history_result = {"status": "failed", "message": str(exc)}

    status = "updated" if cc_switch_changed or result.get("status") == "updated" else str(result.get("status") or "skipped")
    return {
        **result,
        "status": status,
        "source_id": source_id,
        "cc_switch_provider": cc_switch.sanitized_provider(provider),
        "cc_switch_current_updated": cc_switch_changed,
        "history_sync": history_result,
        "db_path": str(db_path),
        "settings_path": str(settings_path),
        "message": result.get("message") or f"已切换到 {provider['name']}。",
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
            return "官方登录 + 第三方 API 会先把 API Key 保存到 provider，再等待你登录 ChatGPT。"
        return "官方登录 + 第三方 API 会把 API Key 写入 provider，并保留移动端、Remote 和原生入口。"
    return "纯 API 会写入 config.toml 和 auth.json，并启用完整增强。"


def provider_profile_apply_message(profile: dict[str, str], action: dict[str, object], failed: bool) -> str:
    if failed:
        reason = str(action.get("reason") or "provider profile apply failed")
        if reason == "chatgpt login token not found":
            return "当前未检测到 ChatGPT 登录态；请先保存 API Key，再登录 ChatGPT。"
        return f"供应商切换失败：{reason}。"
    if profile["mode"] == "official":
        return "已切回官方登录模式；页面增强已设为保留登录态。"
    if profile["mode"] == "mixed-api":
        return "已切换到官方登录 + 第三方 API；官方登录态保护已开启。"
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
    return apply_provider_config_with_auth_payload(
        config_path=config_path,
        auth_path=auth_path,
        mode="mixed-api",
        provider=provider,
        base_url=base_url,
        api_key=api_key,
        wire_api=wire_api,
        model=model,
        auth_payload=None,
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
    auth_payload: dict[str, Any] | None,
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
    updated_auth_text = json.dumps(auth_payload, ensure_ascii=False, indent=2) + "\n" if auth_payload is not None else auth_text
    config_changed = updated_config != config_text
    auth_changed = auth_payload is not None and updated_auth_text != auth_text
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


def set_local_marketplace_in_toml(
    text: str,
    *,
    marketplace_name: str,
    source_path: str,
) -> str:
    lines = text.splitlines(keepends=True)
    section_name = f"marketplaces.{marketplace_name}"
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
        "last_updated": toml_string(datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")),
        "source_type": toml_string("local"),
        "source": toml_string(source_path),
    }
    return "".join(upsert_section_assignments(lines, section_start, section_end, assignments))


def remove_toml_table(text: str, table_name: str) -> str:
    lines = text.splitlines(keepends=True)
    section_start = find_table_start(lines, table_name)
    if section_start is None:
        return text
    section_end = find_next_table_start(lines, section_start + 1)
    del lines[section_start:section_end]
    while len(lines) > 1:
        for index in range(1, len(lines)):
            if lines[index].strip() == "" and lines[index - 1].strip() == "":
                del lines[index]
                break
        else:
            break
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
