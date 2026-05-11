from pathlib import Path


def test_setup_bat_offers_install_and_uninstall_choices():
    text = Path("setup.bat").read_text(encoding="utf-8")

    assert "Codex Mate" in text
    assert "[1]" in text and "install" in text.lower()
    assert "[2]" in text and "uninstall" in text.lower()
    assert "[3]" in text and "update" in text.lower()
    assert "[4]" in text and "logs" in text.lower()
    assert "CodexMate.exe" in text
    assert "CodexMate-windows.zip" in text
    assert "python -m pip install -e ." in text
    assert "CODEX_MATE_PY=python -m codex_mate" in text
    assert "%CODEX_MATE_PY% setup" in text
    assert "%CODEX_MATE_PY% remove" in text
    assert "%CODEX_MATE_PY% update" in text
    assert "%CODEX_MATE_PY% logs" in text
    assert "pause" in text.lower()
