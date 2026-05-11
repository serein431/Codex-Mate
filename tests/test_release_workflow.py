from pathlib import Path


def test_release_workflow_builds_no_python_assets():
    text = Path(".github/workflows/release-assets.yml").read_text(encoding="utf-8")

    assert "CodexMate-windows.zip" in text
    assert "CodexMate-macos.zip" in text
    assert "PyInstaller" in text
    assert "--onefile" in text
    assert "--collect-data codex_mate" in text
    assert "setup.bat" in text
    assert "setup.command" in text
