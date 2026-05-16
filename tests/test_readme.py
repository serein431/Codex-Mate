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
    assert text.index("## 交流群") < text.index("## 主要功能")


def test_readme_includes_codex_mate_icon_and_toc():
    text = Path("README.md").read_text(encoding="utf-8")

    assert "# Codex Mate" in text
    assert '<img src="docs/images/codex-mate.png"' in text
    assert 'width="220"' in text
    assert "## 目录" in text
    assert "- [下载哪个包](#下载哪个包)" in text
    assert "- [Codex 自助安装 Prompt](#codex-自助安装-prompt)" in text
    assert "- [Windows 安装](#windows-安装)" in text
    assert "- [Windows 打开](#windows-打开)" in text
    assert "- [macOS 安装](#macos-安装)" in text
    assert "- [macOS 打开](#macos-打开)" in text
    assert "- [常见问题](#常见问题)" in text
    assert "- [诊断日志](#诊断日志)" in text


    text = Path("README.md").read_text(encoding="utf-8")

    assert "## 友情链接" in text
    assert "[LINUX DO](https://linux.do)" in text
    assert "docs/images/linux-do.png" not in text


def test_readme_describes_transparent_takeover_mode():
    text = Path("README.md").read_text(encoding="utf-8")
    main_text = text.split("## 致谢", 1)[0]

    assert "透明接管" in text
    assert "LaunchAgent" in text
    assert "Codex Mate.lnk" in text
    assert "python -m codex_mate watch-disable" in text
    assert "Windows 默认推荐使用 `Codex Mate.lnk`" in text
    assert "python -m codex_mate doctor --json" in text
    assert LEGACY_BRAND not in main_text
    assert LEGACY_OWNER not in main_text
    assert LEGACY_PROJECT not in main_text
    assert LEGACY_BUNDLE_SUFFIX not in main_text


def test_readme_describes_history_sync_commands():
    text = Path("README.md").read_text(encoding="utf-8")

    assert "## 历史同步" in text
    assert "## 源码安装" in text
    assert "python -m pip install -e ." in text
    assert "历史同步" in text
    assert "python -m codex_mate history-status --json" in text
    assert "python -m codex_mate history-sync --json" in text
    assert "codex_mate_history_backups" in text
    assert "~/.codex/.codex-global-state.json" in text
    assert "重新登录 ChatGPT 账号" in text
    assert "侧边栏历史变空" in text


def test_readme_describes_diagnostic_log_bundle():
    text = Path("README.md").read_text(encoding="utf-8")

    assert "## 诊断日志" in text
    assert "python -m codex_mate logs" in text
    assert "CodexMate-diagnostics" in text
    assert "会自动脱敏" in text


def test_readme_describes_one_click_install_script():
    text = Path("README.md").read_text(encoding="utf-8")

    assert "## 下载哪个包" in text
    assert "## Codex 自助安装 Prompt" in text
    assert "## Windows 安装" in text
    assert "## macOS 安装" in text
    assert "CodexMate-windows.zip" in text
    assert "CodexMate-macos.zip" in text
    assert "不需要" in text
    assert "CodexMate.zip" in text
    assert "Code -> Download ZIP" in text
    assert "setup.bat" in text
    assert "setup.command" in text
    assert "Python 3.11" in text
    assert "如果电脑里没有 Python 和 pip" in text


def test_readme_includes_english_codex_install_prompt():
    text = Path("README.md").read_text(encoding="utf-8")

    assert "You are helping me install Codex Mate for the local Codex desktop app." in text
    assert "Download the latest release asset for this OS" in text
    assert "Run the installer" in text
    assert "verify that the Codex Mate menu appears" in text
    assert "star the repository for me" in text
    assert "If starring requires a login or confirmation, stop and ask me first." in text


def test_readme_describes_in_app_update_controls():
    text = Path("README.md").read_text(encoding="utf-8")

    assert "检查更新" in text
    assert "一键更新" in text
    assert "Codex Mate 面板" in text
    assert "选择 `3`，也就是 `Update Codex Mate`" in text
    assert "CodexMate-windows.zip" in text


def test_readme_describes_native_file_tree_entry():
    text = Path("README.md").read_text(encoding="utf-8")

    assert "顶部提供文件列表入口" in text
    assert "## 功能说明" in text
    assert "### 原生文件树入口" in text
    assert "Codex 自己的文件搜索和文件预览能力" in text
    assert "不会在 Codex Mate 里自写一套文件树" in text
    assert "当前工作目录里的一个真实文件名" in text
    assert "256KB" not in text


def test_readme_thanks_related_projects_at_end():
    text = Path("README.md").read_text(encoding="utf-8")

    assert "## 致谢" in text
    assert "https://github.com/BigPizzaV3/CodexPlusPlus" in text
    assert "https://github.com/GODGOD126/codex-history-sync-tool" in text
