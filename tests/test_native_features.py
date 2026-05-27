from pathlib import Path

from codex_mate import native_features


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
