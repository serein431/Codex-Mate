# Codex Mate

<p align="center">
  <img src="docs/images/codex-mate.png" alt="Codex Mate 图标" width="256">
</p>

## 讨论交流

欢迎加入交流群反馈问题、交流使用体验或提出新功能建议：

<img src="docs/images/discussion-group-qr.jpg" alt="Codex Mate 交流群二维码" width="260">

Codex Mate 是一个给 Codex App 使用的本地增强工具。它通过外部 launcher 启动 Codex，再把增强菜单注入到界面里；整个过程不改动 Codex App 的安装文件，也不需要替换 `app.asar`。

它主要解决三类日常问题：

- API Key 模式下插件入口不可用
- 会话列表缺少直接删除能力
- 切换账号、provider 或模型后，本地聊天记录在侧边栏里看起来“消失”

项目地址：[https://github.com/serein431/Codex-Mate](https://github.com/serein431/Codex-Mate)

## 目录

- [快速上手](#快速上手)
- [讨论交流](#讨论交流)
- [使用效果](#使用效果)
- [功能概览](#功能概览)
- [安装方式](#安装方式)
- [Windows 使用](#windows-使用)
- [macOS 使用](#macos-使用)
- [历史同步](#历史同步)
- [透明接管](#透明接管)
- [更新与卸载](#更新与卸载)
- [数据位置](#数据位置)
- [常见问题](#常见问题)
- [友情链接](#友情链接)
- [开发](#开发)
- [致谢](#致谢)

## 快速上手

先克隆并安装到当前 Python 环境：

```bash
git clone https://github.com/serein431/Codex-Mate.git
cd Codex-Mate
python -m pip install -e .
```

第一次建议直接启动试用：

```bash
python -m codex_session_delete launch
```

如果你刚切换过账号、API、provider 或模型，可以先检查本地历史状态：

```bash
python -m codex_session_delete history-status --json
python -m codex_session_delete history-sync --json
```

确认体验正常后，再安装桌面入口和后台接管：

```bash
python -m codex_session_delete setup
```

安装完成后，你仍然可以从原来的 Codex 图标启动。后台 watcher 会在需要时自动把 Codex 切换到 Codex Mate 的增强启动方式。

## 使用效果

API Key 模式下，原生 Codex 的插件入口可能会要求登录 ChatGPT：

![API Key 模式下插件入口不可用](docs/images/pain-plugin-disabled.png)

原生会话列表也只有归档入口，没有直接删除按钮：

![原生会话列表缺少删除能力](docs/images/pain-no-delete-button.png)

通过 Codex Mate 启动后，会话列表悬停时会显示“删除”按钮：

![Codex Mate 解锁插件入口并添加删除按钮](docs/images/solution-plugin-and-delete.png)

顶部菜单可以打开 Codex Mate 面板，集中管理插件入口、删除按钮和菜单栏位置等选项：

![Codex Mate 配置界面](docs/images/settings-panel.png)

## 功能概览

Codex Mate 当前提供这些能力：

- 解锁 API Key 模式下的插件入口
- 允许特殊插件继续显示安装入口
- 在会话列表中加入悬停删除按钮
- 删除前确认，并支持撤销
- 优先走服务端删除；不可用时处理本地 SQLite 会话记录
- 启动前自动同步本地历史到当前 provider/model
- Windows 和 macOS 都支持安装、卸载和透明接管
- 支持从 GitHub Release 检查并安装更新

## 安装方式

环境要求：

- Python 3.11+
- Windows 或 macOS
- 已安装 Codex App

源码安装：

```bash
python -m pip install -e .
```

需要运行测试时安装测试依赖：

```bash
python -m pip install -e .[test]
python -m pytest -q
```

## Windows 使用

如果你喜欢图形菜单，可以双击项目根目录的：

```text
setup.bat
```

菜单会提供安装、卸载和更新入口：

```text
[1] Install Codex Mate
[2] Uninstall Codex Mate
[3] Update Codex Mate
[4] Exit
```

命令行安装：

```bash
python -m codex_session_delete setup
```

安装后会创建桌面快捷方式：

```text
Codex Mate.lnk
```

同时会注册 Windows 登录自启 watcher。之后即使你从开始菜单、任务栏或原生 Codex 快捷方式打开，watcher 也会检测 Codex 是否带了增强启动所需的 CDP 参数，并在需要时自动接管。

## macOS 使用

命令行安装：

```bash
python -m codex_session_delete setup
```

安装器会自动查找常见的 Codex App 路径，例如：

```text
/Applications/Codex.app
/Applications/OpenAI Codex.app
~/Applications/Codex.app
```

安装后会生成：

```text
/Applications/Codex Mate.app
```

并注册用户级 LaunchAgent：

```text
~/Library/LaunchAgents/dev.codexmate.watcher.plist
```

之后可以继续从 Dock、Spotlight 或原来的 Codex 入口打开，后台 watcher 会负责接管未增强的启动。

## 历史同步

Codex 的本地历史会带有 provider/model 相关信息。切换账号、API、provider 或模型后，旧聊天记录并不一定真的丢了，有时只是和当前配置不匹配，所以侧边栏不再展示。

Codex Mate 会在启动前读取：

```text
~/.codex/config.toml
```

然后把这些本地数据同步到当前配置：

- `~/.codex/state_5.sqlite`
- `~/.codex/sessions/**/rollout-*.jsonl`
- `~/.codex/session_index.jsonl`

查看状态：

```bash
python -m codex_session_delete history-status --json
```

手动同步：

```bash
python -m codex_session_delete history-sync --json
```

同步前会自动备份到：

```text
~/.codex/codex_mate_history_backups
```

这项功能只处理本机已经存在的 Codex 历史文件，不负责把云端账号或另一台电脑上的聊天记录迁移过来。

如果你只想启动 Codex，不想同步历史，可以这样运行：

```bash
python -m codex_session_delete launch --no-history-sync
```

## 透明接管

`setup` 会默认安装透明接管能力。它的作用是让你不必记住“必须从 Codex Mate 启动”：当系统里出现未增强的 Codex 进程时，watcher 会重新拉起带 CDP 参数的 Codex，再完成注入。

单独安装 watcher：

```bash
python -m codex_session_delete watch-install
```

临时关闭或重新开启接管：

```bash
python -m codex_session_delete watch-disable
python -m codex_session_delete watch-enable
```

移除 watcher：

```bash
python -m codex_session_delete watch-remove
```

平台实现：

- Windows 登录自启：`HKCU\Software\Microsoft\Windows\CurrentVersion\Run`，并在 Startup 文件夹创建 `CodexMateWatcher.lnk`
- macOS LaunchAgent：`~/Library/LaunchAgents/dev.codexmate.watcher.plist`

需要注意的是，透明接管可能会让原生 Codex 先闪一下，然后被关闭并重新打开。这是外部 launcher 方案的正常代价。

## 更新与卸载

检查新版本：

```bash
python -m codex_session_delete check-update
```

从 GitHub Release 更新：

```bash
python -m codex_session_delete update
```

更新检查会请求：

```text
https://api.github.com/repos/serein431/Codex-Mate/releases/latest
```

发现新版后会优先下载 Release 里的 `.whl` 文件，并重新执行安装流程。

卸载：

```bash
python -m codex_session_delete remove
```

如果还想删除 Codex Mate 自己产生的日志和备份：

```bash
python -m codex_session_delete remove --remove-data
```

Windows 也可以从“设置 -> 应用 -> 已安装的应用”里卸载 `Codex Mate`。

## 数据位置

Codex Mate 会读取 Codex 本地数据库：

```text
~/.codex/state_5.sqlite
```

会话删除备份：

```text
~/.codex-session-delete/backups
```

历史同步备份：

```text
~/.codex/codex_mate_history_backups
```

启动日志：

```text
~/.codex-session-delete/launcher.log
```

watcher 日志：

```text
~/.codex-session-delete/watcher.log
%USERPROFILE%\.codex-session-delete\watcher.log
```

## 常见问题

### Codex Mate 菜单没有出现

先确认 Codex 是通过 Codex Mate 启动的，或者 watcher 已经启用。也可以检查 Codex 进程是否带有：

```text
--remote-debugging-port=9229
```

### 双击后没有反应

优先查看启动日志：

```text
~/.codex-session-delete/launcher.log
%USERPROFILE%\.codex-session-delete\launcher.log
```

常见原因包括 Codex App 路径变化、9229 端口被占用、Python 环境不可用。

### 原生 Codex 打开后又自动关闭

这是透明接管在工作。watcher 发现当前 Codex 没有以增强参数启动，就会关闭它并重新通过 Codex Mate 启动。

### 切换账号后历史还是没显示

先执行：

```bash
python -m codex_session_delete history-status --json
```

如果状态显示本地没有可同步的会话文件，说明当前机器上可能没有对应历史。历史同步只处理本机已有文件，不会从另一个账号或设备下载聊天记录。

### Windows 卸载失败

先重新安装一次当前版本，再执行卸载：

```bash
python -m codex_session_delete setup
python -m codex_session_delete remove
```

## 友情链接

- [LINUX DO](https://linux.do)

## 开发

常用测试命令：

```bash
python -m pytest -q
```

主要目录：

```text
codex_session_delete/
  cli.py                 命令行入口
  launcher.py            启动 Codex 并完成注入
  cdp.py                 Chromium DevTools Protocol 通信
  helper_server.py       本地 helper 服务
  storage_adapter.py     本地 SQLite 删除与撤销
  history_sync.py        本地历史 provider/model 同步
  autostart.py           Windows/macOS watcher 自启注册
  watcher.py             透明接管进程
  inject/renderer-inject.js

tests/
```

Codex Mate 是外部增强工具。Codex App 更新后，如果界面结构变化，可能需要同步调整注入脚本。

## 致谢

感谢以下项目提供了重要参考和启发：

- [CodexPlusPlus](https://github.com/BigPizzaV3/CodexPlusPlus)：外部 launcher、CDP 注入和 Codex 本地增强方向。
- [codex-history-sync-tool](https://github.com/GODGOD126/codex-history-sync-tool)：Codex 本地历史 provider/model 对齐和备份恢复思路。
