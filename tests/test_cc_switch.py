import json
import sqlite3

import pytest

from codex_mate import cc_switch


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


def test_list_codex_providers_parses_config_auth_and_orders(tmp_path):
    db_path = tmp_path / ".cc-switch" / "cc-switch.db"
    config = (
        'model_provider = "custom"\n'
        'model = "gpt-5.5"\n'
        "\n"
        "[model_providers.custom]\n"
        'name = "Custom"\n'
        'base_url = "https://relay.example/v1"\n'
        'wire_api = "chat"\n'
        "requires_openai_auth = true\n"
    )
    create_cc_switch_db(
        db_path,
        [
            ("later", "codex", "Later", json.dumps({"base_url": "https://later.example/v1", "api_key": "sk-later"}), 1, 10, 0),
            ("current", "codex", "Current", json.dumps({"config": config, "auth": {"OPENAI_API_KEY": "sk-auth"}}), 2, 1, 1),
            ("claude", "claude", "Claude", json.dumps({"base_url": "https://claude.example/v1", "api_key": "sk"}), 0, 0, 0),
            ("bad", "codex", "Bad", "{not json", 3, 2, 0),
        ],
    )

    providers = cc_switch.list_codex_providers(db_path, login_ready=True)

    assert [provider["source_id"] for provider in providers] == ["current", "later"]
    current = providers[0]
    assert current["name"] == "Current"
    assert current["is_current"] is True
    assert current["mode"] == "mixed-api"
    assert current["provider"] == "custom"
    assert current["model"] == "gpt-5.5"
    assert current["base_url"] == "https://relay.example/v1"
    assert current["wire_api"] == "chat"
    assert current["api_key_present"] is True
    assert current["config_present"] is True
    assert current["auth_present"] is True
    assert "api_key" not in current


def test_list_codex_providers_parses_experimental_bearer_token_from_config(tmp_path):
    db_path = tmp_path / ".cc-switch" / "cc-switch.db"
    config = (
        'model_provider = "relay"\n'
        "\n"
        "[model_providers.relay]\n"
        'base_url = "https://relay.example/v1"\n'
        'experimental_bearer_token = "sk-from-config"\n'
    )
    create_cc_switch_db(db_path, [("relay", "codex", "Relay", json.dumps({"config": config}), 1, 1, 0)])

    provider = cc_switch.raw_codex_providers(db_path, login_ready=True)[0]
    sanitized = cc_switch.sanitized_provider(provider)

    assert provider["api_key"] == "sk-from-config"
    assert sanitized["api_key_present"] is True
    assert sanitized["mode"] == "mixed-api"


def test_list_codex_providers_parses_direct_api_shape(tmp_path):
    db_path = tmp_path / ".cc-switch" / "cc-switch.db"
    create_cc_switch_db(
        db_path,
        [
            (
                "direct",
                "codex",
                "Direct",
                json.dumps({"base_url": "https://direct.example/v1", "api_key": "sk-direct", "api_format": "chat-completions"}),
                1,
                1,
                0,
            )
        ],
    )

    provider = cc_switch.list_codex_providers(db_path, login_ready=False)[0]

    assert provider["mode"] == "pure-api"
    assert provider["provider"] == "direct"
    assert provider["base_url"] == "https://direct.example/v1"
    assert provider["wire_api"] == "chat"
    assert provider["api_key_present"] is True
    assert provider["config_present"] is False
    assert provider["auth_present"] is False


def test_list_codex_providers_recognizes_official_empty_config(tmp_path):
    db_path = tmp_path / ".cc-switch" / "cc-switch.db"
    create_cc_switch_db(db_path, [("official", "codex", "OpenAI Official", json.dumps({"config": "", "auth": {}}), 1, 1, 1)])

    provider = cc_switch.list_codex_providers(db_path, login_ready=True)[0]

    assert provider["mode"] == "official"
    assert provider["provider"] == "openai"
    assert provider["base_url"] == ""
    assert provider["api_key_present"] is False


def test_set_current_codex_provider_updates_db_and_settings(tmp_path):
    ccs_home = tmp_path / ".cc-switch"
    db_path = ccs_home / "cc-switch.db"
    settings_path = ccs_home / "settings.json"
    ccs_home.mkdir(parents=True)
    settings_path.write_text('{"currentProviderCodex":"old","language":"zh"}\n', encoding="utf-8")
    create_cc_switch_db(
        db_path,
        [
            ("old", "codex", "Old", json.dumps({"base_url": "https://old.example/v1", "api_key": "sk-old"}), 1, 1, 1),
            ("new", "codex", "New", json.dumps({"base_url": "https://new.example/v1", "api_key": "sk-new"}), 2, 2, 0),
        ],
    )

    changed = cc_switch.set_current_codex_provider(db_path, settings_path, "new")

    assert changed is True
    with sqlite3.connect(db_path) as conn:
        rows = dict(conn.execute("SELECT id, is_current FROM providers WHERE app_type = 'codex'").fetchall())
    assert rows == {"old": 0, "new": 1}
    assert json.loads(settings_path.read_text(encoding="utf-8"))["currentProviderCodex"] == "new"
    assert json.loads(settings_path.read_text(encoding="utf-8"))["language"] == "zh"


def test_get_codex_provider_raises_for_missing_provider(tmp_path):
    db_path = tmp_path / ".cc-switch" / "cc-switch.db"
    create_cc_switch_db(db_path, [("one", "codex", "One", json.dumps({"base_url": "https://one.example/v1", "api_key": "sk-one"}), 1, 1, 0)])

    with pytest.raises(cc_switch.CcSwitchError, match="provider not found"):
        cc_switch.get_codex_provider(db_path, "missing", login_ready=True)


def test_missing_db_returns_empty_provider_list(tmp_path):
    assert cc_switch.list_codex_providers(tmp_path / ".cc-switch" / "missing.db", login_ready=True) == []
