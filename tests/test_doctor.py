from pathlib import Path

from codex_mate import doctor


def test_doctor_collects_windows_direct_launcher_status(monkeypatch, tmp_path):
    monkeypatch.setattr(doctor.sys, "platform", "win32")
    monkeypatch.setattr(doctor.runtime, "is_frozen", lambda: False)
    monkeypatch.setattr(doctor.watcher, "watcher_disabled_flag", lambda: tmp_path / "watcher.disabled")
    monkeypatch.setattr(doctor.watcher, "watcher_lock_path", lambda debug_port: tmp_path / f"watcher-{debug_port}.lock")
    monkeypatch.setattr(doctor.app_paths, "codex_app_dir_cache_path", lambda: tmp_path / "codex_app_dir.txt")
    monkeypatch.setattr(doctor.app_paths, "resolve_codex_app_dir", lambda: Path("C:/Codex/app"))
    monkeypatch.setattr(doctor, "port_listening", lambda port: port == 57321)
    monkeypatch.setattr(doctor, "collect_mobile_remote_status", lambda: {"ready": True})
    (tmp_path / "watcher.disabled").touch()
    (tmp_path / "codex_app_dir.txt").write_text("C:/Codex/app", encoding="utf-8")

    payload = doctor.collect_status()

    assert payload["platform"] == "win32"
    assert payload["watcher"]["enabled"] is False
    assert payload["watcher"]["lock_exists"] is False
    assert payload["ports"]["helper_57321"] is True
    assert payload["ports"]["cdp_9229"] is False
    assert payload["codex_app"]["cache_exists"] is True
    assert payload["codex_app"]["resolved_dir"] == "C:/Codex/app"
    assert payload["mobile_remote"] == {"ready": True}


def test_doctor_reports_mobile_remote_ready_when_chatgpt_auth_is_preserved(tmp_path):
    (tmp_path / "auth.json").write_text('{"auth_mode":"chatgpt","OPENAI_API_KEY":null}\n', encoding="utf-8")
    (tmp_path / "config.toml").write_text(
        'model_provider = "custom"\n'
        '[model_providers.custom]\n'
        'name = "custom"\n'
        'requires_openai_auth = true\n'
        '\n'
        '[features]\n'
        'local_remote_dropdown = true\n'
        'cloud_follow_up_local_remote_dropdown = true\n'
        'remote_conversation_apply_diff = true\n',
        encoding="utf-8",
    )

    payload = doctor.collect_mobile_remote_status(tmp_path)

    assert payload["ready"] is True
    assert payload["auth_mode"] == "chatgpt"
    assert payload["model_provider"] == "custom"
    assert payload["provider_requires_openai_auth"] is True
    assert payload["remote_feature_flags"]["ready"] is True
    assert payload["warnings"] == []


def test_doctor_warns_when_mobile_remote_auth_prerequisites_are_missing(tmp_path):
    (tmp_path / "auth.json").write_text('{"auth_mode":"apikey","OPENAI_API_KEY":"sk-test"}\n', encoding="utf-8")
    (tmp_path / "config.toml").write_text(
        'model_provider = "custom"\n'
        '[model_providers.custom]\n'
        'name = "custom"\n',
        encoding="utf-8",
    )

    payload = doctor.collect_mobile_remote_status(tmp_path)

    assert payload["ready"] is False
    assert payload["auth_mode"] == "apikey"
    assert payload["openai_api_key_present"] is True
    assert payload["provider_requires_openai_auth"] is False
    assert "auth_mode_is_not_chatgpt" in payload["warnings"]
    assert "openai_api_key_is_set" in payload["warnings"]
    assert "provider_requires_openai_auth_is_not_true" in payload["warnings"]


def test_doctor_reports_login_preserving_provider_status(tmp_path):
    (tmp_path / "auth.json").write_text(
        '{"auth_mode":"chatgpt","tokens":{"refresh_token":"tok"}}\n',
        encoding="utf-8",
    )
    (tmp_path / "config.toml").write_text(
        'model_provider = "custom"\n'
        '[model_providers.custom]\n'
        'name = "custom"\n'
        'requires_openai_auth = true\n'
        'base_url = "https://relay.example.test/v1"\n'
        'experimental_bearer_token = "sk-test"\n'
        '\n'
        '[features]\n'
        'local_remote_dropdown = true\n'
        'cloud_follow_up_local_remote_dropdown = true\n'
        'remote_conversation_apply_diff = true\n',
        encoding="utf-8",
    )

    payload = doctor.collect_mobile_remote_status(tmp_path)

    login_provider = payload["login_preserving_provider"]
    assert login_provider["ready"] is True
    assert login_provider["provider"] == "custom"
    assert login_provider["chatgpt_login_token_present"] is True
    assert login_provider["provider_has_bearer_token"] is True
    assert login_provider["auth_openai_api_key_present"] is False
    assert payload["provider_mode"]["mode"] == "mixed-api"
    assert payload["provider_mode"]["provider"] == "custom"
