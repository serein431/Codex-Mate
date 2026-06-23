from pathlib import Path


def test_readme_limits_discussion_group_qr_size():
    text = Path("README.md").read_text(encoding="utf-8")

    assert '<img src="docs/images/discussion-group-qr.png"' in text
    assert 'width="260"' in text
    assert '![Codex Mate 交流群二维码](docs/images/discussion-group-qr.jpg)' not in text
    assert text.index("## 交流群") < text.index("## 主要功能")
    assert text.index("## 推荐中转站") < text.index("## 主要功能")
    assert '<img src="docs/images/ai-agent-group-qr.jpg"' in text
    assert 'alt="AI Agent 交流群二维码"' in text
    assert "docs/images/corvus-relay-group-qr.jpg" not in text
    assert "[https://corvusapi.org/](https://corvusapi.org/)" in text
    assert "[https://jmrai.net/dashboard/overview](https://jmrai.net/dashboard/overview)" in text


def test_readme_includes_codex_mate_icon_and_toc():
    text = Path("README.md").read_text(encoding="utf-8")

    assert "# Codex Mate" in text
    assert '<img src="docs/images/codex-mate.png"' in text
    assert 'width="220"' in text
    assert "## 目录" in text
    assert "- [2.1 更新重点](#21-更新重点)" in text
    assert "- [2.0 更新重点](#20-更新重点)" in text
    assert "- [推荐使用路径](#推荐使用路径)" in text
    assert "- [下载哪个包](#下载哪个包)" in text
    assert "- [Codex 自助安装 Prompt](#codex-自助安装-prompt)" in text
    assert "- [Windows 安装](#windows-安装)" in text
    assert "- [Windows 打开](#windows-打开)" in text
    assert "- [macOS 安装](#macos-安装)" in text
    assert "- [macOS 打开](#macos-打开)" in text
    assert "- [常见问题](#常见问题)" in text
    assert "- [诊断日志](#诊断日志)" in text
    assert "- [命令行速查](#命令行速查)" in text
    assert "- [数据与备份位置](#数据与备份位置)" in text


    text = Path("README.md").read_text(encoding="utf-8")

    assert "## 友情链接" in text
    assert "[LINUX DO](https://linux.do)" in text
    assert "docs/images/linux-do.png" not in text


def test_readme_describes_2_0_user_path_and_storage_locations():
    text = Path("README.md").read_text(encoding="utf-8")

    assert "## 2.1 更新重点" in text
    assert "右侧问题节点" in text
    assert "## 2.0 更新重点" in text
    assert "官方登录态保护面板" in text
    assert "没检测到 ChatGPT token 时，不会把官方登录态保护显示成已开启" in text
    assert "## 推荐使用路径" in text
    assert "点“保护官方登录”" in text
    assert "仅使用兼容模式" in text
    assert "## 命令行速查" in text
    assert "python -m codex_mate launch --no-native-feature-sync" in text
    assert "## 数据与备份位置" in text
    assert "~/.codex-mate/settings.json" in text
    assert "~/.codex/codex_mate_auth_backups/" in text
    assert "~/.codex/sessions/**/rollout-*.jsonl" in text


def test_readme_describes_transparent_takeover_mode():
    text = Path("README.md").read_text(encoding="utf-8")

    assert "透明接管" in text
    assert "LaunchAgent" in text
    assert "Codex Mate.lnk" in text
    assert "python -m codex_mate watch-disable" in text
    assert "Windows 默认推荐使用 `Codex Mate.lnk`" in text
    assert "macOS 继续打开原生 Codex" in text
    assert "python -m codex_mate doctor --json" in text


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


def test_readme_describes_mobile_remote_troubleshooting():
    text = Path("README.md").read_text(encoding="utf-8")

    assert "### 移动端或 Remote 入口不见了" in text
    assert "### Provider 模式" in text
    assert "供应商配置" in text
    assert "切换供应商" in text
    assert "普通用户只需要" in text
    assert "provider_profile" in text
    assert "“官方登录态保护”区域会继续显示当前状态" in text
    assert "~/.codex-mate/settings.json" in text
    assert "官方登录态保护" in text
    assert "强制注入" in text
    assert "我已登录，重新检测" in text
    assert "API Key 已保存" in text
    assert "先把第三方 API Key 写进 provider" in text
    assert '"mobile_remote"' in text
    assert '"login_preserving_provider"' in text
    assert '"provider_mode"' in text
    assert '"mode": "mixed-api"' in text
    assert '"auth_mode": "chatgpt"' in text
    assert '"remote_feature_flags"' in text
    assert "python -m codex_mate provider-mode status --json" in text
    assert "python -m codex_mate provider-mode official" in text
    assert "python -m codex_mate provider-mode mixed-api" in text
    assert "python -m codex_mate provider-mode pure-api" in text
    assert "experimental_bearer_token" in text
    assert "requires_openai_auth = true" in text
    assert "local_remote_dropdown = true" in text
    assert "remote_feature_*_is_not_true" in text
    assert "auth_mode_is_not_chatgpt" in text
    assert "provider_requires_openai_auth_is_not_true" in text


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
    assert "安装后不会再创建额外的 `Codex Mate.app` 快捷方式" in text
    assert "重新安装或卸载时会自动清理这个旧入口" in text
    assert "Spotlight 搜索 `Codex Mate`" not in text


def test_readme_includes_english_codex_install_prompt():
    text = Path("README.md").read_text(encoding="utf-8")

    assert "You are helping me install Codex Mate for the local Codex desktop app." in text
    assert "Download the latest release asset for this OS" in text
    assert "Run the installer" in text
    assert "mobile/remote readiness" in text
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


def test_readme_describes_export_cc_switch_and_scroll_restore():
    text = Path("README.md").read_text(encoding="utf-8")

    assert "role-specific-plugins" in text
    assert "Product Design" in text
    assert "Role-Specific Plugins" in text
    assert "导出当前对话为 Markdown" in text
    assert "移动会话到普通对话或其他项目" in text
    assert "CC Switch 速切" in text
    assert "~/.cc-switch/cc-switch.db" in text
    assert "## 功能说明" in text
    assert "### Markdown 导出" in text
    assert "读取本机 Codex sqlite 数据库" in text
    assert "### 会话移动" in text
    assert "侧边栏里已有的项目" in text
    assert "### 对话节点预览" in text
    assert "读取本机 Codex sqlite 数据库和当前会话对应的 rollout 文件" in text
    assert "右侧原点" in text
    assert "默认最多显示 30 条" in text
    assert "### 滚动位置恢复" in text
    assert "上次看到的位置" in text
    assert "用户问题时间线" not in text
    assert "对话时间线" not in text
    assert "原生文件树入口" not in text
    assert "256KB" not in text


def test_readme_thanks_related_projects_at_end():
    text = Path("README.md").read_text(encoding="utf-8")

    assert "## 致谢" in text
    assert "https://github.com/GODGOD126/codex-history-sync-tool" in text
