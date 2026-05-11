from pathlib import Path


def test_setup_command_offers_install_and_uninstall_choices():
    path = Path("setup.command")
    text = path.read_text(encoding="utf-8")

    assert text.startswith("#!/bin/sh")
    assert "Codex Mate Setup" in text
    assert "[1]" in text and "Install Codex Mate" in text
    assert "[2]" in text and "Uninstall Codex Mate" in text
    assert "[3]" in text and "Update Codex Mate" in text
    assert 'CODEX_MATE_BIN="./CodexMate"' in text
    assert "CodexMate-macos.zip" in text
    assert "-m pip install -e ." in text
    assert '-m codex_mate "$@"' in text
    assert "run_codex_mate setup" in text
    assert "run_codex_mate remove" in text
    assert "run_codex_mate update" in text


def test_setup_command_is_executable():
    mode = Path("setup.command").stat().st_mode

    assert mode & 0o111
