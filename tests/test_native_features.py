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
