from pathlib import Path


LEGACY_BRAND = "Codex" + "++"
LEGACY_OWNER = "Big" + "Pizza" + "V3"
LEGACY_PROJECT = "Codex" + "Plus" + "Plus"
LEGACY_BUNDLE_SUFFIX = "codex" + "plus" + "plus"


def test_readme_limits_discussion_group_qr_size():
    text = Path("README.md").read_text(encoding="utf-8")

    assert '<img src="docs/images/discussion-group-qr.jpg"' in text
    assert 'width="260"' in text
    assert '![Codex Mate 交流群二维码](docs/images/discussion-group-qr.jpg)' not in text
    assert text.index("## 讨论交流") < text.index("Codex Mate 是一个给 Codex App 使用的本地增强工具")


def test_readme_includes_codex_mate_icon_and_toc():
    text = Path("README.md").read_text(encoding="utf-8")

    assert "# Codex Mate" in text
    assert '<img src="docs/images/codex-mate.png"' in text
    assert 'width="256"' in text
    assert "## 目录" in text
    assert "- [Windows 使用](#windows-使用)" in text
    assert "- [常见问题](#常见问题)" in text


    text = Path("README.md").read_text(encoding="utf-8")

    assert "## 友情链接" in text
    assert "[LINUX DO](https://linux.do)" in text
    assert "docs/images/linux-do.png" not in text


def test_readme_describes_transparent_takeover_mode():
    text = Path("README.md").read_text(encoding="utf-8")
    main_text = text.split("## 致谢", 1)[0]

    assert "透明接管" in text
    assert "LaunchAgent" in text
    assert "Windows 登录自启" in text
    assert "python -m codex_session_delete watch-disable" in text
    assert LEGACY_BRAND not in main_text
    assert LEGACY_OWNER not in main_text
    assert LEGACY_PROJECT not in main_text
    assert LEGACY_BUNDLE_SUFFIX not in main_text


def test_readme_describes_history_sync_commands():
    text = Path("README.md").read_text(encoding="utf-8")

    assert "## 快速上手" in text
    assert "python -m pip install -e ." in text
    assert "历史同步" in text
    assert "python -m codex_session_delete history-status --json" in text
    assert "python -m codex_session_delete history-sync --json" in text
    assert "codex_mate_history_backups" in text


def test_readme_thanks_related_projects_at_end():
    text = Path("README.md").read_text(encoding="utf-8")

    assert "## 致谢" in text
    assert "https://github.com/BigPizzaV3/CodexPlusPlus" in text
    assert "https://github.com/GODGOD126/codex-history-sync-tool" in text
