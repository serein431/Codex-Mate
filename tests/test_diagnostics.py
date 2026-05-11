from __future__ import annotations

import zipfile

from codex_mate import diagnostics


def test_redact_text_masks_common_secrets():
    text = "Authorization: Bearer sk-test123456\napi_key = \"abc123\"\nnormal line"

    redacted = diagnostics.redact_text(text)

    assert "sk-test123456" not in redacted
    assert "abc123" not in redacted
    assert "[REDACTED]" in redacted
    assert "normal line" in redacted


def test_collect_diagnostics_writes_zip_with_redacted_logs(tmp_path, monkeypatch):
    data_root = tmp_path / ".codex-mate"
    codex_home = tmp_path / ".codex"
    data_root.mkdir()
    codex_home.mkdir()
    (data_root / "launcher.log").write_text("failed with token sk-secret-123456\n", encoding="utf-8")
    (data_root / "watcher.log").write_text("watcher ok\n", encoding="utf-8")
    (codex_home / "config.toml").write_text('model_provider = "cm"\napi_key = "secret-value"\n', encoding="utf-8")
    monkeypatch.setattr(diagnostics, "run_process_snapshot", lambda: "999 CodexMate.exe --token sk-process-secret\n")

    archive = diagnostics.collect_diagnostics(data_root=data_root, codex_home=codex_home)

    assert archive.exists()
    assert archive.parent == data_root / "diagnostics"
    with zipfile.ZipFile(archive) as bundle:
        names = set(bundle.namelist())
        assert "summary.txt" in names
        assert "logs/launcher.log" in names
        assert "logs/watcher.log" in names
        assert "codex/config.toml" in names
        assert "processes.txt" in names
        launcher_log = bundle.read("logs/launcher.log").decode("utf-8")
        config = bundle.read("codex/config.toml").decode("utf-8")
        processes = bundle.read("processes.txt").decode("utf-8")

    assert "sk-secret-123456" not in launcher_log
    assert "secret-value" not in config
    assert "sk-process-secret" not in processes
    assert "[REDACTED]" in launcher_log


def test_append_log_creates_component_log(tmp_path):
    diagnostics.append_log("support", "hello", data_root=tmp_path)

    text = (tmp_path / "support.log").read_text(encoding="utf-8")
    assert "hello" in text
    assert "[INFO]" in text
