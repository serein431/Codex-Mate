# Codex Mate

<p align="center">
  <img src="docs/images/codex-mate.png" alt="Codex Mate 图标" width="220">
</p>

Codex Mate 是一个给 Codex App 使用的本地增强工具。它通过外部 launcher 启动 Codex，再把增强菜单注入到界面里；不修改 Codex App 原始安装文件，也不替换 `app.asar`。

项目地址：[https://github.com/serein431/Codex-Mate](https://github.com/serein431/Codex-Mate)

## 交流群

欢迎加入交流群反馈问题、交流使用体验或提出新功能建议：

<img src="docs/images/discussion-group-qr.png" alt="Codex Mate 交流群二维码" width="260">

## 主要功能

- 解锁 API Key 模式下的插件入口
- 允许特殊插件继续显示安装入口
- 在会话列表悬停显示“删除”按钮
- 在会话列表悬停导出当前对话为 Markdown
- 在会话列表悬停移动会话到普通对话或其他项目
- 删除前确认，并支持撤销
- 在对话右侧显示问题时间线，并记住每个会话的滚动位置
- 切换账号、provider 或模型后，帮助恢复本机已有聊天记录的侧边栏显示
- 支持 Windows / macOS 安装、更新、卸载和诊断日志导出

## 目录

- [下载哪个包](#下载哪个包)
- [Codex 自助安装 Prompt](#codex-自助安装-prompt)
- [Windows 安装](#windows-安装)
- [Windows 打开](#windows-打开)
- [Windows 更新与卸载](#windows-更新与卸载)
- [macOS 安装](#macos-安装)
- [macOS 打开](#macos-打开)
- [macOS 更新与卸载](#macos-更新与卸载)
- [使用效果](#使用效果)
- [功能说明](#功能说明)
- [历史同步](#历史同步)
- [透明接管](#透明接管)
- [诊断日志](#诊断日志)
- [常见问题](#常见问题)
- [开发](#开发)
- [致谢](#致谢)

## 下载哪个包

打开最新 Release：

[https://github.com/serein431/Codex-Mate/releases/latest](https://github.com/serein431/Codex-Mate/releases/latest)

按系统下载对应文件：

| 系统 | 推荐下载 | 是否需要 Python |
| --- | --- | --- |
| Windows | `CodexMate-windows.zip` | 不需要 |
| macOS | `CodexMate-macos.zip` | 不需要 |
| 源码安装 | `CodexMate.zip` 或 `Code -> Download ZIP` | 需要 Python 3.11+ |

如果电脑里没有 Python 和 pip，请下载平台包，也就是 `CodexMate-windows.zip` 或 `CodexMate-macos.zip`。

如果双击安装脚本时提示找不到 Python，通常是下载错了源码包。重新下载对应系统的平台包即可。

## Codex 自助安装 Prompt

可以把下面这段英文 prompt 交给 Codex，让它在当前电脑上自动安装 Codex Mate：

```text
You are helping me install Codex Mate for the local Codex desktop app.

Please do the following end to end:

1. Open the project page: https://github.com/serein431/Codex-Mate
2. Detect my operating system.
3. Download the latest release asset for this OS:
   - Windows: CodexMate-windows.zip
   - macOS: CodexMate-macos.zip
4. Extract the archive into a stable local folder.
5. Run the installer:
   - Windows: run setup.bat and choose "Install Codex Mate"
   - macOS: run setup.command and choose "Install Codex Mate"
6. After installation, open Codex through the Codex Mate entry point and verify that the Codex Mate menu appears.
7. Run the built-in doctor command if available and summarize whether CDP, helper, watcher, mobile/remote readiness, and injection look healthy.
8. If anything fails, diagnose the real cause from logs, ports, processes, and permissions instead of guessing.

After Codex Mate is installed and verified, please open https://github.com/serein431/Codex-Mate and star the repository for me if GitHub is signed in. If starring requires a login or confirmation, stop and ask me first.
```

## Windows 安装

1. 确认电脑里已经安装 Codex App。
2. 从 Release 下载 `CodexMate-windows.zip`。
3. 解压 ZIP 到一个固定位置，例如桌面或 `D:\Tools\CodexMate`。
4. 双击解压后的 `setup.bat`。
5. 在菜单里输入 `1`，选择 `Install Codex Mate`。
6. 看到安装成功提示后关闭窗口。

`setup.bat` 菜单大致如下：

```text
[1] Install Codex Mate
[2] Uninstall Codex Mate
[3] Update Codex Mate
[4] Export diagnostic logs
[5] Enable transparent watcher
[6] Disable transparent watcher
[7] Doctor
[8] Exit
```

安装后会创建桌面快捷方式：

```text
Codex Mate.lnk
```

## Windows 打开

推荐从桌面的 `Codex Mate.lnk` 打开。

这条启动方式最稳定：它会直接用 Codex Mate 拉起 Codex，不需要 watcher 先关闭原生 Codex 再重新打开，因此更少闪窗口，也更不容易出现接管失败。

如果你想继续从原生 Codex 图标、开始菜单或任务栏固定项打开，可以启用透明接管：

1. 双击 `setup.bat`
2. 选择 `5`，也就是 `Enable transparent watcher`

启用后，watcher 会在后台发现普通 Codex 进程，并自动切换到 Codex Mate 增强启动方式。

## Windows 更新与卸载

更新：

1. 双击 `setup.bat`
2. 选择 `3`，也就是 `Update Codex Mate`
3. 更新完成后关闭 Codex，再重新从 `Codex Mate.lnk` 打开

卸载：

1. 双击 `setup.bat`
2. 选择 `2`，也就是 `Uninstall Codex Mate`

也可以在 Windows 的“设置 -> 应用 -> 已安装的应用”里卸载 `Codex Mate`。

如果更新后界面里仍显示旧版本，通常是启动了旧文件夹里的 `CodexMate.exe`，或旧 watcher 还没退出。最稳的做法是关闭 Codex，重新下载最新 `CodexMate-windows.zip`，解压到新目录，再运行 `setup.bat` 选择 `1` 安装。

## macOS 安装

1. 确认电脑里已经安装 Codex App。
2. 从 Release 下载 `CodexMate-macos.zip`。
3. 解压 ZIP。
4. 右键 `setup.command`，选择“打开”。
5. 在菜单里输入 `1`，选择 `Install Codex Mate`。
6. 看到安装成功提示后关闭窗口。

如果 macOS 提示无法打开，请不要直接双击，改用右键“打开”。

安装器会自动查找常见 Codex App 路径，例如：

```text
/Applications/Codex.app
/Applications/OpenAI Codex.app
~/Applications/Codex.app
```

安装后会生成：

```text
/Applications/Codex Mate.app
```

同时会注册用户级 LaunchAgent：

```text
~/Library/LaunchAgents/dev.codexmate.watcher.plist
```

## macOS 打开

安装后可以从以下任意入口打开：

- `/Applications/Codex Mate.app`
- Spotlight 搜索 `Codex Mate`
- Dock 里的 Codex Mate
- 原来的 Codex 入口

macOS 默认会安装透明接管 watcher。也就是说，即使你从原来的 Codex 入口打开，Codex Mate 也会尝试自动完成增强启动和注入。

如果只想临时启动一次，也可以在终端运行：

```bash
python -m codex_mate launch
```

## macOS 更新与卸载

更新推荐方式：

1. 下载最新 `CodexMate-macos.zip`
2. 解压
3. 右键打开 `setup.command`
4. 选择 `1` 重新安装

卸载：

1. 打开 `setup.command`
2. 选择 `2`，也就是 `Uninstall Codex Mate`

命令行卸载：

```bash
python -m codex_mate remove
```

如果还想删除 Codex Mate 自己产生的日志和备份：

```bash
python -m codex_mate remove --remove-data
```

## 使用效果

API Key 模式下，原生 Codex 的插件入口可能会要求登录 ChatGPT：

![API Key 模式下插件入口不可用](docs/images/pain-plugin-disabled.png)

原生会话列表只有归档入口，没有直接删除按钮：

![原生会话列表缺少删除能力](docs/images/pain-no-delete-button.png)

通过 Codex Mate 启动后，会话列表悬停时会显示“删除”按钮：

![Codex Mate 解锁插件入口并添加删除按钮](docs/images/solution-plugin-and-delete.png)

顶部菜单可以打开 Codex Mate 面板，集中管理功能开关、检查更新和问题反馈：

![Codex Mate 配置界面](docs/images/settings-panel.png)

## 功能说明

### 插件入口解锁

Codex Mate 会让 API Key 模式下的插件入口显示并可用，适合使用自定义 provider、API Key 或切换工具的用户。

### 会话删除

会话列表悬停时会出现“删除”按钮。点击后会先弹出确认框，删除成功后会显示提示，并尽量支持撤销。

删除优先走 Codex 可用的服务端接口；如果不可用，再处理本机 SQLite 和本地索引。

### Markdown 导出

会话列表悬停时会出现“导出 Markdown”按钮。点击后，Codex Mate 会读取本机 `state_5.sqlite` 里的会话记录和对应 rollout 文件，把用户与助手消息整理成一个 `.md` 文件。

导出只读取本机已有聊天记录，不会上传内容，也不会改写 Codex 的数据库。

### 会话移动

会话列表悬停时会出现“移动会话”按钮。点击后可以把当前会话移到“普通对话”，也可以移到侧边栏里已有的项目。

移动会同步本机 SQLite、rollout 文件和 Codex 的侧边栏状态文件。界面会尽量马上把这一行挪到目标位置；如果当前侧边栏没有展开或没有对应目标，重启或刷新 Codex 后也会按新的归属显示。

### 对话时间线与滚动恢复

对话页右侧会显示用户问题时间线。长对话里可以直接点击标记跳到对应问题，少翻很多屏。

Codex Mate 也会记住每个会话的阅读位置。切换到别的会话再回来时，会尽量回到上次看到的位置，避免 Codex 自动滚到最底部。

### 检查更新

打开 Codex Mate 面板后，可以点击“检查更新”。如果当前安装方式支持自动更新，会出现“一键更新”按钮。

也可以用命令行检查：

```bash
python -m codex_mate check-update
python -m codex_mate update
```

## 历史同步

Codex 的本地历史会带有 provider/model 相关信息。切换账号、API、provider 或模型后，旧聊天记录有时并没有丢，只是和当前配置不匹配，所以侧边栏不再展示。

Codex Mate 会读取：

```text
~/.codex/config.toml
```

然后同步这些本地数据：

```text
~/.codex/state_5.sqlite
~/.codex/sessions/**/rollout-*.jsonl
~/.codex/session_index.jsonl
~/.codex/.codex-global-state.json
```

如果 `config.toml` 里没有显式写 `model_provider`，Codex Mate 会按官方默认 provider `openai` 处理。部分切换工具在切回官方模型时只写 `model`，这种情况下也可以直接运行历史同步。

查看状态：

```bash
python -m codex_mate history-status --json
```

手动同步：

```bash
python -m codex_mate history-sync --json
```

如果重新登录 ChatGPT 账号后侧边栏历史变空，可以这样处理：

1. 退出 Codex。
2. 运行 `python -m codex_mate history-sync --json`。
3. 重新打开 Codex。

同步前会自动备份到：

```text
~/.codex/codex_mate_history_backups
```

这项功能只处理本机已经存在的 Codex 历史文件，不会从云端账号或另一台电脑下载聊天记录。

如果只想启动 Codex，不想同步历史：

```bash
python -m codex_mate launch --no-history-sync
```

## 透明接管

透明接管是可选能力。它的作用是让你不必记住“必须从 Codex Mate 启动”。

当系统里出现未增强的 Codex 进程时，watcher 会重新拉起带调试端口的 Codex，再完成注入。

Windows 默认推荐使用 `Codex Mate.lnk`，不强依赖 watcher。macOS 默认会安装 LaunchAgent 来保持原有体验。

命令行：

```bash
python -m codex_mate watch-install
python -m codex_mate watch-disable
python -m codex_mate watch-enable
python -m codex_mate watch-remove
```

查看当前启动状态：

```bash
python -m codex_mate doctor --json
```

需要注意：透明接管可能会让原生 Codex 先闪一下，然后被关闭并重新打开。这是外部 launcher 方案的正常代价。

## 诊断日志

如果遇到闪退、删除按钮无反应、注入失败、历史记录异常等问题，可以导出诊断包发给维护者。

Windows：

1. 双击 `setup.bat`
2. 选择 `4`，也就是 `Export diagnostic logs`

macOS：

1. 打开 `setup.command`
2. 选择 `4`，也就是 `Export diagnostic logs`

命令行：

```bash
python -m codex_mate logs
```

诊断包位置类似：

```text
~/.codex-mate/diagnostics/CodexMate-diagnostics-20260512-003000.zip
%USERPROFILE%\.codex-mate\diagnostics\CodexMate-diagnostics-20260512-003000.zip
```

诊断包会包含 Codex Mate 的启动日志、watcher 日志、进程快照和必要配置摘要，并会自动脱敏常见 API Key、Bearer Token、`sk-...` 等敏感字段。

## 常见问题

### Codex Mate 菜单没有出现

优先确认你是从 Codex Mate 入口启动的。

Windows 推荐从桌面 `Codex Mate.lnk` 打开。macOS 可以从 `/Applications/Codex Mate.app` 打开。

也可以运行：

```bash
python -m codex_mate doctor --json
```

重点看 Codex 进程是否带有：

```text
--remote-debugging-port=9229
```

### 移动端或 Remote 入口不见了

移动端和 Remote 入口属于 Codex 原生功能。Codex Mate 不会删除这些入口；它只通过外部启动和注入增强菜单、插件入口、会话删除、导出、移动和时间线。

如果更新或切换 provider 后这两个入口消失，先运行：

```bash
python -m codex_mate doctor --json
```

重点看输出里的 `mobile_remote`：

```json
{
  "mobile_remote": {
    "ready": true,
    "auth_mode": "chatgpt",
    "openai_api_key_present": false,
    "model_provider": "openai",
    "provider_requires_openai_auth": true,
    "remote_feature_flags": {
      "ready": true,
      "missing": []
    },
    "warnings": []
  }
}
```

一般需要同时满足：

- `~/.codex/auth.json` 里 `auth_mode` 是 `chatgpt`
- `OPENAI_API_KEY` 没有被写成实际 Key
- 当前 `model_provider` 对应的 provider 配置里有 `requires_openai_auth = true`
- `~/.codex/config.toml` 的 `[features]` 里启用了原生 Remote 相关开关：`local_remote_dropdown = true`、`cloud_follow_up_local_remote_dropdown = true`、`remote_conversation_apply_diff = true`

Codex Mate 正常启动时会自动补齐这些 Remote 开关，并在修改前备份 `config.toml` 到 `~/.codex/codex_mate_config_backups/`。如果 `warnings` 里出现 `auth_mode_is_not_chatgpt`、`openai_api_key_is_set`、`provider_requires_openai_auth_is_not_true` 或 `remote_feature_*_is_not_true`，说明当前 Codex 运行态还不满足原生移动端或 Remote 入口的显示条件。修复后需要重启 Codex，让新配置进入当前窗口。

### 双击安装脚本后提示找不到 Python

你大概率下载的是源码包。

没有 Python 的用户请下载：

- Windows：`CodexMate-windows.zip`
- macOS：`CodexMate-macos.zip`

### 原生 Codex 打开后又自动关闭

这是透明接管在工作。watcher 发现当前 Codex 没有以增强参数启动，就会关闭它并重新通过 Codex Mate 启动。

Windows 如果不想要这种行为，可以打开 `setup.bat`，选择 `6` 关闭 watcher，然后固定从 `Codex Mate.lnk` 打开。

### 切换账号后历史还是没显示

先执行：

```bash
python -m codex_mate history-status --json
```

如果状态显示本地没有可同步的会话文件，说明当前机器上可能没有对应历史。历史同步只处理本机已有文件，不会从另一个账号或设备下载聊天记录。

### Windows 更新后还是旧版本

关闭 Codex，重新下载最新 `CodexMate-windows.zip`，解压到一个新目录，再运行 `setup.bat` 选择 `1` 安装。

如果之前启用了 watcher，也可以先在 `setup.bat` 里选择 `6` 关闭 watcher，再重新安装。

### Windows 卸载失败

先重新安装一次当前版本，再卸载：

```bash
python -m codex_mate setup
python -m codex_mate remove
```

也可以用 `setup.bat` 里的 `Uninstall Codex Mate`。

## 源码安装

源码安装适合开发者，或者已经有 Python 3.11+ 的用户。

```bash
git clone https://github.com/serein431/Codex-Mate.git
cd Codex-Mate
python -m pip install -e .
python -m codex_mate launch
```

不使用 Git 时，也可以下载源码 ZIP，解压后运行：

```bash
python -m pip install -e .
python -m codex_mate setup
```

## 开发

安装测试依赖：

```bash
python -m pip install -e .[test]
```

运行测试：

```bash
python -m pytest -q
```

主要目录：

```text
codex_mate/
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

## 友情链接

- [LINUX DO](https://linux.do)

## 致谢

感谢以下项目提供了重要参考和启发：

- [CodexPlusPlus](https://github.com/BigPizzaV3/CodexPlusPlus)：外部 launcher、CDP 注入和 Codex 本地增强方向。
- [codex-history-sync-tool](https://github.com/GODGOD126/codex-history-sync-tool)：Codex 本地历史 provider/model 对齐和备份恢复思路。
