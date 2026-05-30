from pathlib import Path
import json
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


def test_ensure_login_preserving_provider_moves_api_key_out_of_auth(tmp_path):
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
    assert "OPENAI_API_KEY" not in auth
    assert Path(payload["config_backup_path"]).exists()
    assert Path(payload["auth_backup_path"]).exists()


def test_ensure_login_preserving_provider_skips_without_chatgpt_tokens(tmp_path):
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

    assert payload["status"] == "skipped"
    assert payload["reason"] == "chatgpt login token not found"
    assert native_features.read_json_object(auth_path)["OPENAI_API_KEY"] == "sk-auth"
    assert "requires_openai_auth" not in config_path.read_text(encoding="utf-8")


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


def test_apply_mixed_api_provider_mode_requires_chatgpt_tokens(tmp_path):
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

    assert payload["status"] == "skipped"
    assert payload["reason"] == "chatgpt login token not found"
    assert native_features.read_json_object(codex_home / "auth.json")["OPENAI_API_KEY"] == "sk-old"


def test_apply_mixed_api_provider_mode_writes_config_without_auth_api_key(tmp_path):
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
    assert "OPENAI_API_KEY" not in auth


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
    assert payload["auth_enhancement_mode"] == "loginPreserving"
    assert config["model_provider"] == "jmrai"
    assert config["model"] == "gpt-5.5"
    assert provider["requires_openai_auth"] is True
    assert provider["experimental_bearer_token"] == "sk-new"
    assert "OPENAI_API_KEY" not in auth
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
        '{"auth_mode":"chatgpt","OPENAI_API_KEY":"sk-old","tokens":{"refresh_token":"tok"}}\n',
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
    history_calls = []
    monkeypatch.setattr(native_features.history_sync, "resolve_paths", lambda home: ("paths", home))
    monkeypatch.setattr(native_features.history_sync, "sync_history_if_ready", lambda paths: history_calls.append(paths) or {"status": "skipped"})

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
    assert "OPENAI_API_KEY" not in auth
    assert history_calls == [("paths", codex_home)]
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
    monkeypatch.setattr(native_features.history_sync, "resolve_paths", lambda home: ("paths", home))
    monkeypatch.setattr(native_features.history_sync, "sync_history_if_ready", lambda paths: {"status": "skipped"})

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


def test_apply_cc_switch_provider_switches_official_provider(tmp_path, monkeypatch):
    codex_home = tmp_path / ".codex"
    settings_home = tmp_path / ".codex-mate"
    ccs_home = tmp_path / ".cc-switch"
    codex_home.mkdir()
    (codex_home / "auth.json").write_text('{"auth_mode":"chatgpt","OPENAI_API_KEY":"sk-old","tokens":{"access_token":"tok"}}\n', encoding="utf-8")
    (codex_home / "config.toml").write_text('model_provider = "custom"\n[model_providers.custom]\nbase_url = "https://old.example/v1"\n', encoding="utf-8")
    create_cc_switch_db(ccs_home / "cc-switch.db", [("official", "codex", "OpenAI Official", json.dumps({"config": "", "auth": {}}), 1, 1, 0)])
    monkeypatch.setattr(native_features.history_sync, "resolve_paths", lambda home: ("paths", home))
    monkeypatch.setattr(native_features.history_sync, "sync_history_if_ready", lambda paths: {"status": "skipped"})

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
    assert payload["auth_enhancement_mode"] == "loginPreserving"
    assert payload["provider_action"]["status"] == "updated"
    assert provider["requires_openai_auth"] is True
    assert provider["experimental_bearer_token"] == "sk-auth"
    assert "OPENAI_API_KEY" not in auth


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


def test_login_preserving_mode_recovers_chatgpt_auth_mode_when_tokens_survive_api_switch(tmp_path):
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
    assert auth["auth_mode"] == "chatgpt"
    assert auth["tokens"]["refresh_token"] == "tok"
    assert "OPENAI_API_KEY" not in auth
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


def test_set_auth_enhancement_mode_login_preserving_fails_without_chatgpt_login(tmp_path):
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

    assert payload["status"] == "failed"
    assert payload["auth_enhancement_mode"] == "forceInject"
    assert payload["login_preserving_available"] is False
    assert "请先在 Codex 中登录 ChatGPT" in payload["message"]
    assert not (settings_home / "settings.json").exists()
    assert native_features.read_json_object(auth_path)["OPENAI_API_KEY"] == "sk-auth"
