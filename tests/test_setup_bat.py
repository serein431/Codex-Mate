from pathlib import Path


def test_setup_bat_offers_install_and_uninstall_choices():
    text = Path("setup.bat").read_text(encoding="utf-8")

    assert "Codex Mate" in text
    assert "[1]" in text and "install" in text.lower()
    assert "[2]" in text and "uninstall" in text.lower()
    assert "[3]" in text and "update" in text.lower()
    assert "python -m pip install -e ." in text
    assert "python -m codex_session_delete setup" in text
    assert "python -m codex_session_delete remove" in text
    assert "python -m codex_session_delete update" in text
    assert "pause" in text.lower()
