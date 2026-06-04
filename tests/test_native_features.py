from pathlib import Path
import json
import shutil
import sqlite3

from codex_mate import native_features


def create_cc_switch_db(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE providers ("
            "id TEXT NOT NULL, "
            "app_type TEXT NOT NULL, "
            "name TEXT NOT NULL, "
            "settings_config TEXT NOT NULL, "
            "created_at INTEGER, "
            "sort_index INTEGER, "
            "is_current BOOLEAN NOT NULL DEFAULT 0, "
            "PRIMARY KEY (id, app_type)"
            ")"
        )
        conn.executemany(
            "INSERT INTO providers (id, app_type, name, settings_config, created_at, sort_index, is_current) VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )


def write_bundled_plugin(root: Path, name: str, version: str = "1.0.0") -> None:
    plugin_dir = root / "plugins" / name / ".codex-plugin"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / "plugin.json").write_text(
        json.dumps({"name": name, "version": version}),
        encoding="utf-8",
    )


def write_bundled_marketplace(root: Path, names: list[str]) -> None:
    manifest_path = root / ".agents" / "plugins" / "marketplace.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "name": "openai-bundled",
                "interface": {"version": 1},
                "plugins": [{"name": name, "source": {"source": "local", "path": f"./plugins/{name}"}} for name in names],
            }
        ),
        encoding="utf-8",
    )


def write_curated_marketplace(root: Path, names: list[str], marketplace_name: str = "openai-curated") -> None:
    manifest_path = root / ".agents" / "plugins" / "marketplace.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "name": marketplace_name,
                "interface": {"version": 1},
                "plugins": [{"name": name, "source": {"source": "local", "path": f"./plugins/{name}"}} for name in names],
            }
        ),
        encoding="utf-8",
    )
    for name in names:
        write_bundled_plugin(root, name)


def test_remote_feature_status_reports_missing_flags(tmp_path):
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    (codex_home / "config.toml").write_text(
        "[features]\n"
        "codex_hooks = true\n",
        encoding="utf-8",
    )

    payload = native_features.remote_feature_status(codex_home)

    assert payload["ready"] is False
    assert payload["enabled"] == {"codex_hooks": True}
    assert "local_remote_dropdown" in payload["missing"]
    assert "cloud_follow_up_local_remote_dropdown" in payload["missing"]


def test_ensure_bundled_plugin_marketplace_cache_copies_new_codex_plugins(tmp_path):
    codex_home = tmp_path / ".codex"
    source_root = tmp_path / "Codex.app" / "Contents" / "Resources" / "plugins" / "openai-bundled"
    cache_root = codex_home / ".tmp" / "bundled-marketplaces" / "openai-bundled"
    write_bundled_marketplace(source_root, ["browser", "chrome", "sites"])
    write_bundled_plugin(source_root, "browser", "1.0.0")
    write_bundled_plugin(source_root, "chrome", "1.0.0")
    write_bundled_plugin(source_root, "sites", "2.0.0")
    write_bundled_marketplace(cache_root, ["browser", "chrome"])
    write_bundled_plugin(cache_root, "browser", "1.0.0")
    write_bundled_plugin(cache_root, "chrome", "1.0.0")

    payload = native_features.ensure_bundled_plugin_marketplace_cache(codex_home, app_dir=tmp_path / "Codex.app")

    assert payload["status"] == "updated"
    assert payload["ready"] is True
    assert payload["source_plugins"] == {"browser": "1.0.0", "chrome": "1.0.0", "sites": "2.0.0"}
    assert native_features.bundled_plugin_signature(cache_root) == payload["source_plugins"]


def test_ensure_bundled_plugin_marketplace_cache_skips_when_current(tmp_path):
    codex_home = tmp_path / ".codex"
    source_root = tmp_path / "Codex.app" / "Contents" / "Resources" / "plugins" / "openai-bundled"
    cache_root = codex_home / ".tmp" / "bundled-marketplaces" / "openai-bundled"
    for root in (source_root, cache_root):
        write_bundled_marketplace(root, ["browser"])
        write_bundled_plugin(root, "browser", "1.0.0")

    payload = native_features.ensure_bundled_plugin_marketplace_cache(codex_home, app_dir=tmp_path / "Codex.app")

    assert payload["status"] == "skipped"
    assert payload["ready"] is True


def test_ensure_curated_plugin_marketplace_registered_adds_local_marketplace(tmp_path):
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    marketplace_root = codex_home / ".tmp" / "plugins"
    alias_root = codex_home / ".tmp" / "codex-mate-marketplaces" / "openai-bundled"
    config_path = codex_home / "config.toml"
    config_path.write_text(
        "[marketplaces.openai-bundled]\n"
        'source_type = "local"\n'
        f"source = {json.dumps(str(alias_root))}\n"
        "\n"
        "[marketplaces.openai-curated]\n"
        'source_type = "local"\n'
        f"source = {json.dumps(str(marketplace_root))}\n"
        "\n"
        '[plugins."browser@openai-bundled"]\n'
        "enabled = true\n",
        encoding="utf-8",
    )
    write_curated_marketplace(marketplace_root, ["linear", "notion"])

    payload = native_features.ensure_curated_plugin_marketplace_registered(codex_home)

    config = native_features.read_config(config_path)
    assert payload["status"] == "updated"
    assert payload["ready"] is True
    assert payload["plugin_count"] == 2
    assert payload["alias_ready"] is False
    assert "openai-bundled" not in config["marketplaces"]
    assert config["marketplaces"]["openai-curated"]["source_type"] == "local"
    assert config["marketplaces"]["openai-curated"]["source"] == str(marketplace_root)
    assert config["plugins"]["browser@openai-bundled"]["enabled"] is True
    assert Path(payload["backup_path"]).exists()


def test_ensure_curated_plugin_marketplace_registered_skips_when_source_missing(tmp_path):
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    config_path = codex_home / "config.toml"
    config_path.write_text("", encoding="utf-8")

    payload = native_features.ensure_curated_plugin_marketplace_registered(codex_home)

    assert payload["status"] == "skipped"
    assert payload["source_ready"] is False
    assert "openai-bundled" not in config_path.read_text(encoding="utf-8")


def test_ensure_curated_plugin_marketplace_registered_skips_when_already_registered(tmp_path):
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    marketplace_root = codex_home / ".tmp" / "plugins"
    config_path = codex_home / "config.toml"
    write_curated_marketplace(marketplace_root, ["linear"])
    config_path.write_text(
        "[marketplaces.openai-curated]\n"
        'last_updated = "2026-06-03T00:00:00Z"\n'
        'source_type = "local"\n'
        f"source = {json.dumps(str(marketplace_root))}\n",
        encoding="utf-8",
    )

    payload = native_features.ensure_curated_plugin_marketplace_registered(codex_home)

    assert payload["status"] == "skipped"
    assert payload["ready"] is True
    assert not (codex_home / "codex_mate_config_backups").exists()


def test_ensure_curated_plugin_marketplace_registered_skips_invalid_plugin_paths(tmp_path):
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    marketplace_root = codex_home / ".tmp" / "plugins"
    config_path = codex_home / "config.toml"
    config_path.write_text("", encoding="utf-8")
    write_curated_marketplace(marketplace_root, ["linear"])
    shutil.rmtree(marketplace_root / "plugins" / "linear")

    payload = native_features.ensure_curated_plugin_marketplace_registered(codex_home)

    assert payload["status"] == "skipped"
    assert payload["invalid_plugins"] == ["linear"]
    assert "openai-bundled" not in config_path.read_text(encoding="utf-8")


def test_ensure_remote_feature_flags_updates_existing_features_section(tmp_path):
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    config_path = codex_home / "config.toml"
    config_path.write_text(
        'model_provider = "custom"\n'
        "\n"
        "[features]\n"
        "codex_hooks = true\n"
        "local_remote_dropdown = false\n"
        "\n"
        "[desktop]\n"
        "keepRemoteControlAwakeWhilePluggedIn = true\n",
        encoding="utf-8",
    )

    payload = native_features.ensure_remote_feature_flags(codex_home)

    text = config_path.read_text(encoding="utf-8")
    assert payload["status"] == "updated"
    assert "local_remote_dropdown = true" in text
    assert "cloud_follow_up_local_remote_dropdown = true" in text
    assert "remote_conversation_apply_diff = true" in text
    assert "[desktop]\nkeepRemoteControlAwakeWhilePluggedIn = true" in text
    assert Path(payload["backup_path"]).exists()

    second = native_features.ensure_remote_feature_flags(codex_home)

    assert second["status"] == "skipped"
    assert second["reason"] == "remote feature flags already enabled"


def test_ensure_remote_feature_flags_appends_features_section_when_missing(tmp_path):
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    config_path = codex_home / "config.toml"
    config_path.write_text('model_provider = "custom"\n', encoding="utf-8")

    payload = native_features.ensure_remote_feature_flags(codex_home)

    assert payload["status"] == "updated"
    assert "[features]" in config_path.read_text(encoding="utf-8")


def test_ensure_remote_feature_flags_preserves_valid_toml_without_final_newline(tmp_path):
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    config_path = codex_home / "config.toml"
    config_path.write_text("[features]\ncodex_hooks = true", encoding="utf-8")

    payload = native_features.ensure_remote_feature_flags(codex_home)

    assert payload["status"] == "updated"
    assert native_features.read_config(config_path)["features"]["local_remote_dropdown"] is True


def test_ensure_login_preserving_provider_copies_api_key_without_rewriting_auth(tmp_path):
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    auth_path = codex_home / "auth.json"
    config_path = codex_home / "config.toml"
    auth_path.write_text(
        '{"auth_mode":"chatgpt","OPENAI_API_KEY":"sk-auth","tokens":{"access_token":"tok"}}\n',
        encoding="utf-8",
    )
    config_path.write_text(
        'model_provider = "custom"\n'
        'OPENAI_API_KEY = "sk-root"\n'
        '\n'
        '[model_providers.custom]\n'
        'name = "Custom"\n'
        'wire_api = "chat"\n'
        'requires_openai_auth = false\n'
        'base_url = "https://relay.example.test/v1"\n',
        encoding="utf-8",
    )

    payload = native_features.ensure_login_preserving_provider(codex_home)

    config = native_features.read_config(config_path)
    auth = native_features.read_json_object(auth_path)
    provider = config["model_providers"]["custom"]
    assert payload["status"] == "updated"
    assert payload["provider"] == "custom"
    assert provider["requires_openai_auth"] is True
    assert provider["experimental_bearer_token"] == "sk-auth"
    assert "OPENAI_API_KEY" not in config
    assert auth["auth_mode"] == "chatgpt"
    assert auth["tokens"]["access_token"] == "tok"
    assert auth["OPENAI_API_KEY"] == "sk-auth"
    assert Path(payload["config_backup_path"]).exists()
    assert payload["auth_backup_path"] == ""


def test_ensure_login_preserving_provider_prepares_api_key_before_chatgpt_login(tmp_path):
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    auth_path = codex_home / "auth.json"
    config_path = codex_home / "config.toml"
    auth_path.write_text('{"auth_mode":"apikey","OPENAI_API_KEY":"sk-auth"}\n', encoding="utf-8")
    config_path.write_text(
        'model_provider = "custom"\n'
        '\n'
        '[model_providers.custom]\n'
        'base_url = "https://relay.example.test/v1"\n',
        encoding="utf-8",
    )

    payload = native_features.ensure_login_preserving_provider(codex_home)

    config = native_features.read_config(config_path)
    provider = config["model_providers"]["custom"]
    assert payload["status"] == "updated"
    assert payload["reason"] == "login-preserving provider prepared; waiting for ChatGPT login"
    assert native_features.read_json_object(auth_path)["OPENAI_API_KEY"] == "sk-auth"
    assert provider["requires_openai_auth"] is True
    assert provider["experimental_bearer_token"] == "sk-auth"


def test_apply_official_provider_mode_clears_api_mode_without_removing_chatgpt_tokens(tmp_path):
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    auth_path = codex_home / "auth.json"
    config_path = codex_home / "config.toml"
    auth_path.write_text(
        '{"auth_mode":"chatgpt","OPENAI_API_KEY":"sk-auth","tokens":{"refresh_token":"tok"}}\n',
        encoding="utf-8",
    )
    config_path.write_text(
        'model_provider = "custom"\n'
        'OPENAI_API_KEY = "sk-root"\n'
        '\n'
        '[model_providers.custom]\n'
        'base_url = "https://relay.example.test/v1"\n',
        encoding="utf-8",
    )

    payload = native_features.apply_provider_mode(codex_home, mode="official")

    auth = native_features.read_json_object(auth_path)
    config_text = config_path.read_text(encoding="utf-8")
    assert payload["status"] == "updated"
    assert payload["mode"] == "official"
    assert auth["auth_mode"] == "chatgpt"
    assert auth["tokens"]["refresh_token"] == "tok"
    assert "OPENAI_API_KEY" not in auth
    assert 'model_provider = "custom"' not in config_text
    assert 'OPENAI_API_KEY = "sk-root"' not in config_text


def test_apply_mixed_api_provider_mode_prepares_config_before_chatgpt_login(tmp_path):
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    (codex_home / "auth.json").write_text('{"auth_mode":"apikey","OPENAI_API_KEY":"sk-old"}\n', encoding="utf-8")
    (codex_home / "config.toml").write_text("", encoding="utf-8")

    payload = native_features.apply_provider_mode(
        codex_home,
        mode="mixed-api",
        provider="custom",
        base_url="https://relay.example.test/v1",
        api_key="sk-new",
    )

    config = native_features.read_config(codex_home / "config.toml")
    provider = config["model_providers"]["custom"]
    assert payload["status"] == "updated"
    assert payload["reason"] == "mixed-api provider mode enabled"
    assert provider["experimental_bearer_token"] == "sk-new"
    assert native_features.read_json_object(codex_home / "auth.json")["OPENAI_API_KEY"] == "sk-old"


def test_apply_mixed_api_provider_mode_writes_config_without_rewriting_auth(tmp_path):
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    auth_path = codex_home / "auth.json"
    config_path = codex_home / "config.toml"
    auth_path.write_text(
        '{"auth_mode":"chatgpt","OPENAI_API_KEY":"sk-old","tokens":{"id_token":"tok"}}\n',
        encoding="utf-8",
    )
    config_path.write_text("[features]\ncodex_hooks = true\n", encoding="utf-8")

    payload = native_features.apply_provider_mode(
        codex_home,
        mode="mixed-api",
        provider="custom",
        base_url="https://relay.example.test/v1",
        api_key="sk-new",
    )

    config = native_features.read_config(config_path)
    auth = native_features.read_json_object(auth_path)
    provider = config["model_providers"]["custom"]
    assert payload["status"] == "updated"
    assert payload["mode"] == "mixed-api"
    assert config["model_provider"] == "custom"
    assert provider["requires_openai_auth"] is True
    assert provider["experimental_bearer_token"] == "sk-new"
    assert auth["auth_mode"] == "chatgpt"
    assert auth["tokens"]["id_token"] == "tok"
    assert auth["OPENAI_API_KEY"] == "sk-old"


def test_apply_pure_api_provider_mode_writes_full_api_auth(tmp_path):
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    auth_path = codex_home / "auth.json"
    config_path = codex_home / "config.toml"
    auth_path.write_text('{"auth_mode":"chatgpt","tokens":{"access_token":"tok"}}\n', encoding="utf-8")
    config_path.write_text("", encoding="utf-8")

    payload = native_features.apply_provider_mode(
        codex_home,
        mode="pure-api",
        provider="custom",
        base_url="https://relay.example.test/v1",
        api_key="sk-new",
    )

    config = native_features.read_config(config_path)
    auth = native_features.read_json_object(auth_path)
    provider = config["model_providers"]["custom"]
    assert payload["status"] == "updated"
    assert payload["mode"] == "pure-api"
    assert config["model_provider"] == "custom"
    assert provider["requires_openai_auth"] is True
    assert provider["experimental_bearer_token"] == "sk-new"
    assert auth == {"OPENAI_API_KEY": "sk-new"}


def test_apply_provider_profile_mixed_api_saves_profile_and_login_preserving_mode(tmp_path):
    codex_home = tmp_path / ".codex"
    settings_home = tmp_path / ".codex-mate"
    codex_home.mkdir()
    auth_path = codex_home / "auth.json"
    config_path = codex_home / "config.toml"
    auth_path.write_text(
        '{"auth_mode":"chatgpt","OPENAI_API_KEY":"sk-old","tokens":{"refresh_token":"tok"}}\n',
        encoding="utf-8",
    )
    config_path.write_text("[features]\ncodex_hooks = true\n", encoding="utf-8")

    payload = native_features.apply_provider_profile(
        codex_home,
        settings_home=settings_home,
        profile={
            "mode": "mixed-api",
            "provider": "jmrai",
            "base_url": "https://jmrai.example/v1",
            "api_key": "sk-new",
            "model": "gpt-5.5",
            "wire_api": "responses",
        },
    )

    config = native_features.read_config(config_path)
    auth = native_features.read_json_object(auth_path)
    settings = native_features.read_json_object(settings_home / "settings.json")
    provider = config["model_providers"]["jmrai"]
    assert payload["status"] == "updated"
    assert payload["profile"]["api_key_present"] is True
    assert "api_key" not in payload["profile"]
    assert payload["auth_enhancement_mode"] == "forceInject"
    assert payload["desired_auth_enhancement_mode"] == "loginPreserving"
    assert config["model_provider"] == "jmrai"
    assert config["model"] == "gpt-5.5"
    assert provider["requires_openai_auth"] is True
    assert provider["experimental_bearer_token"] == "sk-new"
    assert auth["OPENAI_API_KEY"] == "sk-old"
    assert "覆盖后可启用" in payload["message"]
    assert settings["auth_enhancement_mode"] == "loginPreserving"
    assert settings["provider_profile"]["api_key"] == "sk-new"


def test_apply_provider_profile_mixed_api_prepares_before_chatgpt_login(tmp_path):
    codex_home = tmp_path / ".codex"
    settings_home = tmp_path / ".codex-mate"
    codex_home.mkdir()
    auth_path = codex_home / "auth.json"
    config_path = codex_home / "config.toml"
    auth_path.write_text('{"auth_mode":"apikey","OPENAI_API_KEY":"sk-old"}\n', encoding="utf-8")
    config_path.write_text("", encoding="utf-8")

    payload = native_features.apply_provider_profile(
        codex_home,
        settings_home=settings_home,
        profile={
            "mode": "mixed-api",
            "provider": "jmrai",
            "base_url": "https://jmrai.example/v1",
            "api_key": "sk-new",
            "model": "gpt-5.5",
            "wire_api": "responses",
        },
    )

    config = native_features.read_config(config_path)
    auth = native_features.read_json_object(auth_path)
    settings = native_features.read_json_object(settings_home / "settings.json")
    provider = config["model_providers"]["jmrai"]
    assert payload["status"] == "updated"
    assert payload["auth_enhancement_mode"] == "forceInject"
    assert payload["desired_auth_enhancement_mode"] == "loginPreserving"
    assert payload["provider_api_ready"] is True
    assert "覆盖后可启用" in payload["message"]
    assert auth["OPENAI_API_KEY"] == "sk-old"
    assert provider["experimental_bearer_token"] == "sk-new"
    assert settings["auth_enhancement_mode"] == "loginPreserving"
    assert settings["provider_profile"]["api_key"] == "sk-new"


def test_apply_provider_profile_reuses_saved_api_key_when_form_leaves_key_blank(tmp_path):
    codex_home = tmp_path / ".codex"
    settings_home = tmp_path / ".codex-mate"
    codex_home.mkdir()
    (codex_home / "auth.json").write_text(
        '{"auth_mode":"chatgpt","tokens":{"refresh_token":"tok"}}\n',
        encoding="utf-8",
    )
    (settings_home).mkdir()
    (settings_home / "settings.json").write_text(
        '{"provider_profile":{"mode":"mixed-api","provider":"jmrai","base_url":"https://old.example/v1","api_key":"sk-saved","model":"gpt-old","wire_api":"responses"}}\n',
        encoding="utf-8",
    )

    payload = native_features.apply_provider_profile(
        codex_home,
        settings_home=settings_home,
        profile={
            "mode": "mixed-api",
            "provider": "jmrai",
            "base_url": "https://new.example/v1",
            "api_key": "",
            "model": "gpt-new",
            "wire_api": "responses",
        },
    )

    config = native_features.read_config(codex_home / "config.toml")
    settings = native_features.read_json_object(settings_home / "settings.json")
    provider = config["model_providers"]["jmrai"]
    assert payload["status"] == "updated"
    assert config["model"] == "gpt-new"
    assert provider["base_url"] == "https://new.example/v1"
    assert provider["experimental_bearer_token"] == "sk-saved"
    assert settings["provider_profile"]["api_key"] == "sk-saved"


def test_apply_provider_profile_pure_api_sets_force_inject_mode(tmp_path):
    codex_home = tmp_path / ".codex"
    settings_home = tmp_path / ".codex-mate"
    codex_home.mkdir()
    (codex_home / "auth.json").write_text('{"auth_mode":"chatgpt","tokens":{"access_token":"tok"}}\n', encoding="utf-8")

    payload = native_features.apply_provider_profile(
        codex_home,
        settings_home=settings_home,
        profile={
            "mode": "pure-api",
            "provider": "jmrai",
            "base_url": "https://jmrai.example/v1",
            "api_key": "sk-new",
            "model": "gpt-5.5",
            "wire_api": "responses",
        },
    )

    config = native_features.read_config(codex_home / "config.toml")
    auth = native_features.read_json_object(codex_home / "auth.json")
    settings = native_features.read_json_object(settings_home / "settings.json")
    assert payload["status"] == "updated"
    assert payload["auth_enhancement_mode"] == "forceInject"
    assert payload["pluginEntryUnlock"] is True
    assert config["model_provider"] == "jmrai"
    assert config["model"] == "gpt-5.5"
    assert auth == {"OPENAI_API_KEY": "sk-new"}
    assert settings["auth_enhancement_mode"] == "forceInject"


def test_apply_cc_switch_provider_uses_mixed_api_when_chatgpt_login_exists(tmp_path, monkeypatch):
    codex_home = tmp_path / ".codex"
    settings_home = tmp_path / ".codex-mate"
    ccs_home = tmp_path / ".cc-switch"
    codex_home.mkdir()
    (codex_home / "auth.json").write_text(
        '{"auth_mode":"chatgpt","tokens":{"refresh_token":"tok"}}\n',
        encoding="utf-8",
    )
    config = (
        'model_provider = "custom"\n'
        'model = "gpt-5.5"\n'
        "\n"
        "[model_providers.custom]\n"
        'name = "Custom"\n'
        'base_url = "https://relay.example/v1"\n'
        'wire_api = "responses"\n'
        "requires_openai_auth = true\n"
    )
    create_cc_switch_db(ccs_home / "cc-switch.db", [("p1", "codex", "Relay", json.dumps({"config": config, "auth": {"OPENAI_API_KEY": "sk-new"}}), 1, 1, 0)])
    monkeypatch.setattr(native_features.history_sync, "sync_history_if_ready", lambda paths: (_ for _ in ()).throw(AssertionError("history sync should not run during provider switch")))
    visibility_calls = []
    monkeypatch.setattr(
        native_features.history_sync,
        "sync_history_visibility_if_ready",
        lambda paths: visibility_calls.append(paths) or {"ok": True, "skipped": False, "visibility_only": True},
    )

    payload = native_features.apply_cc_switch_provider(
        codex_home,
        settings_home=settings_home,
        cc_switch_home=ccs_home,
        source_id="p1",
    )

    config_data = native_features.read_config(codex_home / "config.toml")
    auth = native_features.read_json_object(codex_home / "auth.json")
    assert payload["status"] == "updated"
    assert payload["profile"]["mode"] == "mixed-api"
    assert config_data["model_provider"] == "custom"
    assert config_data["model"] == "gpt-5.5"
    assert config_data["model_providers"]["custom"]["experimental_bearer_token"] == "sk-new"
    assert auth == {"auth_mode": "chatgpt", "tokens": {"refresh_token": "tok"}}
    assert payload["history_sync"]["visibility_only"] is True
    assert visibility_calls == [native_features.history_sync.resolve_paths(codex_home)]
    assert json.loads((ccs_home / "settings.json").read_text(encoding="utf-8"))["currentProviderCodex"] == "p1"


def test_apply_cc_switch_provider_uses_pure_api_without_chatgpt_login(tmp_path, monkeypatch):
    codex_home = tmp_path / ".codex"
    settings_home = tmp_path / ".codex-mate"
    ccs_home = tmp_path / ".cc-switch"
    codex_home.mkdir()
    (codex_home / "auth.json").write_text('{"auth_mode":"apikey","OPENAI_API_KEY":"sk-old"}\n', encoding="utf-8")
    create_cc_switch_db(
        ccs_home / "cc-switch.db",
        [("p1", "codex", "Relay", json.dumps({"base_url": "https://relay.example/v1", "api_key": "sk-new", "api_format": "chat"}), 1, 1, 0)],
    )
    monkeypatch.setattr(native_features.history_sync, "sync_history_if_ready", lambda paths: (_ for _ in ()).throw(AssertionError("history sync should not run during provider switch")))
    monkeypatch.setattr(
        native_features.history_sync,
        "sync_history_visibility_if_ready",
        lambda paths: {"ok": True, "skipped": False, "visibility_only": True},
    )

    payload = native_features.apply_cc_switch_provider(
        codex_home,
        settings_home=settings_home,
        cc_switch_home=ccs_home,
        source_id="p1",
    )

    config = native_features.read_config(codex_home / "config.toml")
    auth = native_features.read_json_object(codex_home / "auth.json")
    assert payload["status"] == "updated"
    assert payload["profile"]["mode"] == "pure-api"
    assert config["model_provider"] == "p1"
    assert config["model_providers"]["p1"]["wire_api"] == "chat"
    assert auth == {"OPENAI_API_KEY": "sk-new"}
    assert payload["history_sync"]["visibility_only"] is True


def test_apply_cc_switch_provider_switches_official_provider(tmp_path, monkeypatch):
    codex_home = tmp_path / ".codex"
    settings_home = tmp_path / ".codex-mate"
    ccs_home = tmp_path / ".cc-switch"
    codex_home.mkdir()
    (codex_home / "auth.json").write_text('{"auth_mode":"chatgpt","OPENAI_API_KEY":"sk-old","tokens":{"access_token":"tok"}}\n', encoding="utf-8")
    (codex_home / "config.toml").write_text('model_provider = "custom"\n[model_providers.custom]\nbase_url = "https://old.example/v1"\n', encoding="utf-8")
    create_cc_switch_db(ccs_home / "cc-switch.db", [("official", "codex", "OpenAI Official", json.dumps({"config": "", "auth": {}}), 1, 1, 0)])
    monkeypatch.setattr(native_features.history_sync, "sync_history_if_ready", lambda paths: (_ for _ in ()).throw(AssertionError("history sync should not run during provider switch")))
    monkeypatch.setattr(
        native_features.history_sync,
        "sync_history_visibility_if_ready",
        lambda paths: {"ok": True, "skipped": False, "visibility_only": True},
    )

    payload = native_features.apply_cc_switch_provider(
        codex_home,
        settings_home=settings_home,
        cc_switch_home=ccs_home,
        source_id="official",
    )

    assert payload["status"] == "updated"
    assert payload["profile"]["mode"] == "official"
    assert 'model_provider = "custom"' not in (codex_home / "config.toml").read_text(encoding="utf-8")
    assert "OPENAI_API_KEY" not in native_features.read_json_object(codex_home / "auth.json")
    assert payload["history_sync"]["visibility_only"] is True


def test_apply_cc_switch_provider_does_not_update_external_current_on_failure(tmp_path, monkeypatch):
    codex_home = tmp_path / ".codex"
    settings_home = tmp_path / ".codex-mate"
    ccs_home = tmp_path / ".cc-switch"
    codex_home.mkdir()
    create_cc_switch_db(
        ccs_home / "cc-switch.db",
        [
            ("old", "codex", "Old", json.dumps({"base_url": "https://old.example/v1", "api_key": "sk-old"}), 1, 1, 1),
            ("new", "codex", "New", json.dumps({"base_url": "https://new.example/v1", "api_key": "sk-new"}), 2, 2, 0),
        ],
    )
    (ccs_home / "settings.json").write_text('{"currentProviderCodex":"old"}\n', encoding="utf-8")
    monkeypatch.setattr(native_features, "apply_provider_profile", lambda *args, **kwargs: {"status": "failed", "message": "boom"})

    payload = native_features.apply_cc_switch_provider(
        codex_home,
        settings_home=settings_home,
        cc_switch_home=ccs_home,
        source_id="new",
    )

    assert payload["status"] == "failed"
    with sqlite3.connect(ccs_home / "cc-switch.db") as conn:
        rows = dict(conn.execute("SELECT id, is_current FROM providers WHERE app_type = 'codex'").fetchall())
    assert rows == {"old": 1, "new": 0}
    assert json.loads((ccs_home / "settings.json").read_text(encoding="utf-8"))["currentProviderCodex"] == "old"


def test_apply_cc_switch_provider_reports_invalid_profile_without_updating_current(tmp_path):
    codex_home = tmp_path / ".codex"
    settings_home = tmp_path / ".codex-mate"
    ccs_home = tmp_path / ".cc-switch"
    codex_home.mkdir()
    create_cc_switch_db(
        ccs_home / "cc-switch.db",
        [
            ("old", "codex", "Old", json.dumps({"base_url": "https://old.example/v1", "api_key": "sk-old"}), 1, 1, 1),
            ("broken", "codex", "Broken", json.dumps({"base_url": "https://broken.example/v1"}), 2, 2, 0),
        ],
    )
    (ccs_home / "settings.json").write_text('{"currentProviderCodex":"old"}\n', encoding="utf-8")

    payload = native_features.apply_cc_switch_provider(
        codex_home,
        settings_home=settings_home,
        cc_switch_home=ccs_home,
        source_id="broken",
    )

    assert payload["status"] == "failed"
    assert "api_key is required" in payload["message"]
    with sqlite3.connect(ccs_home / "cc-switch.db") as conn:
        rows = dict(conn.execute("SELECT id, is_current FROM providers WHERE app_type = 'codex'").fetchall())
    assert rows == {"old": 1, "broken": 0}
    assert json.loads((ccs_home / "settings.json").read_text(encoding="utf-8"))["currentProviderCodex"] == "old"


def test_provider_profile_status_returns_sanitized_saved_profile(tmp_path):
    codex_home = tmp_path / ".codex"
    settings_home = tmp_path / ".codex-mate"
    codex_home.mkdir()
    settings_home.mkdir()
    (settings_home / "settings.json").write_text(
        '{"provider_profile":{"mode":"pure-api","provider":"jmrai","base_url":"https://jmrai.example/v1","api_key":"sk-secret","model":"gpt-5.5","wire_api":"responses"}}\n',
        encoding="utf-8",
    )

    payload = native_features.provider_profile_status(codex_home, settings_home=settings_home)

    assert payload["status"] == "ok"
    assert payload["profile"]["mode"] == "pure-api"
    assert payload["profile"]["provider"] == "jmrai"
    assert payload["profile"]["api_key_present"] is True
    assert "api_key" not in payload["profile"]
    assert payload["provider_mode"]["mode"] == "unknown"


def test_auth_enhancement_mode_status_defaults_from_provider_mode(tmp_path):
    codex_home = tmp_path / ".codex"
    settings_home = tmp_path / ".codex-mate"
    codex_home.mkdir()
    (codex_home / "auth.json").write_text(
        '{"auth_mode":"chatgpt","tokens":{"refresh_token":"tok"}}\n',
        encoding="utf-8",
    )
    (codex_home / "config.toml").write_text(
        'model_provider = "custom"\n'
        '[model_providers.custom]\n'
        'requires_openai_auth = true\n'
        'base_url = "https://relay.example.test/v1"\n'
        'experimental_bearer_token = "sk-test"\n',
        encoding="utf-8",
    )

    payload = native_features.auth_enhancement_mode_status(codex_home, settings_home=settings_home)

    assert payload["status"] == "ok"
    assert payload["auth_enhancement_mode"] == "loginPreserving"
    assert payload["pluginEntryUnlock"] is False
    assert payload["forcePluginInstall"] is False
    assert payload["provider_mode"]["mode"] == "mixed-api"
    assert payload["settings_path"] == str(settings_home / "settings.json")


def test_set_auth_enhancement_mode_persists_force_inject_without_rewriting_provider(tmp_path):
    codex_home = tmp_path / ".codex"
    settings_home = tmp_path / ".codex-mate"
    codex_home.mkdir()
    config_path = codex_home / "config.toml"
    config_path.write_text('model_provider = "custom"\n', encoding="utf-8")

    payload = native_features.set_auth_enhancement_mode(
        codex_home,
        settings_home=settings_home,
        mode="forceInject",
    )

    assert payload["status"] == "updated"
    assert payload["auth_enhancement_mode"] == "forceInject"
    assert payload["pluginEntryUnlock"] is True
    assert payload["forcePluginInstall"] is True
    assert native_features.read_json_object(settings_home / "settings.json")["auth_enhancement_mode"] == "forceInject"
    assert config_path.read_text(encoding="utf-8") == 'model_provider = "custom"\n'


def test_set_auth_enhancement_mode_login_preserving_migrates_provider_when_possible(tmp_path):
    codex_home = tmp_path / ".codex"
    settings_home = tmp_path / ".codex-mate"
    codex_home.mkdir()
    auth_path = codex_home / "auth.json"
    config_path = codex_home / "config.toml"
    auth_path.write_text(
        '{"auth_mode":"chatgpt","OPENAI_API_KEY":"sk-auth","tokens":{"access_token":"tok"}}\n',
        encoding="utf-8",
    )
    config_path.write_text(
        'model_provider = "custom"\n'
        '[model_providers.custom]\n'
        'name = "Custom"\n'
        'wire_api = "chat"\n'
        'requires_openai_auth = false\n'
        'base_url = "https://relay.example.test/v1"\n',
        encoding="utf-8",
    )

    payload = native_features.set_auth_enhancement_mode(
        codex_home,
        settings_home=settings_home,
        mode="loginPreserving",
    )

    config = native_features.read_config(config_path)
    auth = native_features.read_json_object(auth_path)
    provider = config["model_providers"]["custom"]
    assert payload["status"] == "updated"
    assert payload["auth_enhancement_mode"] == "forceInject"
    assert payload["desired_auth_enhancement_mode"] == "loginPreserving"
    assert payload["provider_action"]["status"] == "updated"
    assert provider["requires_openai_auth"] is True
    assert provider["experimental_bearer_token"] == "sk-auth"
    assert auth["OPENAI_API_KEY"] == "sk-auth"


def test_set_auth_enhancement_mode_reuses_saved_provider_key_when_live_key_is_missing(tmp_path):
    codex_home = tmp_path / ".codex"
    settings_home = tmp_path / ".codex-mate"
    codex_home.mkdir()
    settings_home.mkdir()
    auth_path = codex_home / "auth.json"
    config_path = codex_home / "config.toml"
    auth_path.write_text(
        '{"auth_mode":"chatgpt","tokens":{"access_token":"tok"}}\n',
        encoding="utf-8",
    )
    config_path.write_text(
        'model_provider = "jmrai"\n'
        '[model_providers.jmrai]\n'
        'name = "jmrai"\n'
        'wire_api = "responses"\n'
        'requires_openai_auth = false\n'
        'base_url = "https://jmrai.example/v1"\n',
        encoding="utf-8",
    )
    (settings_home / "settings.json").write_text(
        '{"provider_profile":{"mode":"mixed-api","provider":"jmrai","base_url":"https://jmrai.example/v1","api_key":"sk-saved","model":"gpt-5.5","wire_api":"responses"}}\n',
        encoding="utf-8",
    )

    payload = native_features.set_auth_enhancement_mode(
        codex_home,
        settings_home=settings_home,
        mode="loginPreserving",
    )

    config = native_features.read_config(config_path)
    provider = config["model_providers"]["jmrai"]
    assert payload["status"] == "updated"
    assert payload["auth_enhancement_mode"] == "loginPreserving"
    assert payload["provider_action"]["status"] == "updated"
    assert provider["requires_openai_auth"] is True
    assert provider["experimental_bearer_token"] == "sk-saved"
    assert config["model"] == "gpt-5.5"


def test_login_preserving_mode_preserves_auth_json_when_tokens_survive_api_switch(tmp_path):
    codex_home = tmp_path / ".codex"
    settings_home = tmp_path / ".codex-mate"
    codex_home.mkdir()
    auth_path = codex_home / "auth.json"
    config_path = codex_home / "config.toml"
    auth_path.write_text(
        '{"auth_mode":"apikey","OPENAI_API_KEY":"sk-auth","tokens":{"refresh_token":"tok"}}\n',
        encoding="utf-8",
    )
    config_path.write_text(
        'model_provider = "custom"\n'
        '[model_providers.custom]\n'
        'name = "Custom"\n'
        'wire_api = "responses"\n'
        'requires_openai_auth = false\n'
        'base_url = "https://relay.example.test/v1"\n',
        encoding="utf-8",
    )

    payload = native_features.set_auth_enhancement_mode(
        codex_home,
        settings_home=settings_home,
        mode="loginPreserving",
    )

    auth = native_features.read_json_object(auth_path)
    config = native_features.read_config(config_path)
    provider = config["model_providers"]["custom"]
    assert payload["status"] == "updated"
    assert payload["provider_action"]["status"] == "updated"
    assert auth["auth_mode"] == "apikey"
    assert auth["tokens"]["refresh_token"] == "tok"
    assert auth["OPENAI_API_KEY"] == "sk-auth"
    assert provider["experimental_bearer_token"] == "sk-auth"


def test_set_auth_enhancement_mode_login_preserving_fails_without_provider_api_key(tmp_path):
    codex_home = tmp_path / ".codex"
    settings_home = tmp_path / ".codex-mate"
    codex_home.mkdir()
    auth_path = codex_home / "auth.json"
    config_path = codex_home / "config.toml"
    auth_path.write_text(
        '{"auth_mode":"chatgpt","tokens":{"refresh_token":"tok"}}\n',
        encoding="utf-8",
    )
    config_path.write_text(
        'model_provider = "custom"\n'
        '[model_providers.custom]\n'
        'name = "Custom"\n'
        'wire_api = "responses"\n'
        'requires_openai_auth = false\n'
        'base_url = "https://relay.example.test/v1"\n',
        encoding="utf-8",
    )

    payload = native_features.set_auth_enhancement_mode(
        codex_home,
        settings_home=settings_home,
        mode="loginPreserving",
    )

    assert payload["status"] == "failed"
    assert payload["provider_action"]["reason"] == "provider api key missing"
    assert "供应商配置" in payload["message"]
    assert "API Key" in payload["message"]
    assert not (settings_home / "settings.json").exists()
    assert "experimental_bearer_token" not in config_path.read_text(encoding="utf-8")


def test_set_auth_enhancement_mode_login_preserving_prepares_api_key_before_chatgpt_login(tmp_path):
    codex_home = tmp_path / ".codex"
    settings_home = tmp_path / ".codex-mate"
    codex_home.mkdir()
    auth_path = codex_home / "auth.json"
    auth_path.write_text('{"auth_mode":"apikey","OPENAI_API_KEY":"sk-auth"}\n', encoding="utf-8")
    (codex_home / "config.toml").write_text(
        'model_provider = "custom"\n'
        '[model_providers.custom]\n'
        'base_url = "https://relay.example.test/v1"\n',
        encoding="utf-8",
    )

    payload = native_features.set_auth_enhancement_mode(
        codex_home,
        settings_home=settings_home,
        mode="loginPreserving",
    )

    config = native_features.read_config(codex_home / "config.toml")
    provider = config["model_providers"]["custom"]
    settings = native_features.read_json_object(settings_home / "settings.json")
    assert payload["status"] == "updated"
    assert payload["auth_enhancement_mode"] == "forceInject"
    assert payload["desired_auth_enhancement_mode"] == "loginPreserving"
    assert payload["login_preserving_available"] is False
    assert payload["provider_api_ready"] is True
    assert "API Key 已保存" in payload["message"]
    assert settings["auth_enhancement_mode"] == "loginPreserving"
    assert native_features.read_json_object(auth_path)["OPENAI_API_KEY"] == "sk-auth"
    assert provider["experimental_bearer_token"] == "sk-auth"
