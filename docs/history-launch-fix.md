# Codex Mate 历史记录与启动接管修复说明

本文记录本次修复的内容、行为变化，以及 Windows 和 macOS 上的使用方式。本文是独立说明，不修改原 README。

## 修复目标

这次修复针对两个用户可见问题：

- 安装 Codex Mate 后，原生 Codex 被 watcher 接管，但注入失败时 Codex 也被关闭，用户看到的是“桌面版打不开”。
- 卸载 Codex Mate 后，Codex 可以重新打开，但项目侧边栏显示 `No chats`，看起来像本地聊天记录丢失。

实际根因更接近：

- watcher/launcher 的失败处理过于激进，注入失败后会清理 Codex 进程。
- `history-sync` 重建 `~/.codex/session_index.jsonl` 时过于激进，可能丢掉新版 Codex 索引中的未知字段或原有条目，导致历史文件仍在但 UI 索引不到。

## 本次改动

### 1. 保留原默认功能

本次修复不关闭项目原有默认能力：

- `python -m codex_session_delete setup` 仍默认安装 watcher。
- `python -m codex_session_delete launch` 仍默认执行历史同步。

如果用户需要临时避开这些能力，可以显式使用开关：

```bash
python -m codex_session_delete setup --no-watcher
python -m codex_session_delete launch --no-history-sync
```

### 2. 注入失败时不再关闭 Codex

`launcher.py` 现在在注入失败时只关闭 Codex Mate helper server 并抛出错误，不再额外杀掉已经启动的 Codex 进程。

这样 watcher 接管失败时，用户最多得到一个没有注入成功的 Codex 窗口，而不是 Codex 被反复关闭。

### 3. 历史索引改为保守更新

`history_sync.rebuild_session_index()` 现在会先读取已有的 `session_index.jsonl`，再保守更新：

- 对已存在条目，只更新 `id`、`thread_name`、`updated_at`。
- 保留已有条目的未知字段，例如新版 Codex 可能新增的 workspace、路径、来源等字段。
- 保留原索引中数据库未覆盖到的条目，避免同步时把仍可能有效的记录从索引里删除。
- 对数据库里存在但索引里缺失的 active thread，再追加最小索引项。

这能降低“同步后历史文件还在，但侧栏显示 No chats”的风险。

### 4. 新增历史恢复命令

新增命令：

```bash
python -m codex_session_delete history-restore --json
```

默认恢复 `~/.codex/codex_mate_history_backups` 中最新的 Codex Mate 备份。

也可以指定备份：

```bash
python -m codex_session_delete history-restore --backup <state_5.sqlite.*.bak> --json
```

恢复会处理：

- `state_5.sqlite`
- 对应的 `session_index.jsonl` 备份
- `sessions/**/rollout-*.jsonl` 的首行 `session_meta` 快照

恢复前会先创建一个新的 `pre-restore` 备份，避免覆盖当前状态后无法回退。

## Windows 使用方式

### 安装本地源码版本

在项目根目录执行：

```powershell
python -m pip install -e .
```

### 默认安装

```powershell
python -m codex_session_delete setup
```

默认会：

- 创建桌面 `Codex Mate.lnk`
- 注册并启动 watcher
- 让原生 Codex 启动也能被 Codex Mate 接管

### 不安装 watcher

如果只想测试桌面快捷方式，不想接管原生 Codex：

```powershell
python -m codex_session_delete setup --no-watcher
```

### 启动

默认启动并同步历史：

```powershell
python -m codex_session_delete launch
```

跳过历史同步启动：

```powershell
python -m codex_session_delete launch --no-history-sync
```

### 查看历史状态

```powershell
python -m codex_session_delete history-status --json
```

### 手动同步历史

```powershell
python -m codex_session_delete history-sync --json
```

同步前会备份到：

```text
%USERPROFILE%\.codex\codex_mate_history_backups
```

### 恢复历史备份

恢复最新备份：

```powershell
python -m codex_session_delete history-restore --json
```

恢复指定备份：

```powershell
python -m codex_session_delete history-restore --backup "$env:USERPROFILE\.codex\codex_mate_history_backups\state_5.sqlite.pre-sync.YYYYMMDD-HHMMSS.bak" --json
```

### watcher 管理

安装 watcher：

```powershell
python -m codex_session_delete watch-install
```

临时禁用：

```powershell
python -m codex_session_delete watch-disable
```

重新启用：

```powershell
python -m codex_session_delete watch-enable
```

移除：

```powershell
python -m codex_session_delete watch-remove
```

### 卸载

```powershell
python -m codex_session_delete remove
```

删除 Codex Mate 自有数据：

```powershell
python -m codex_session_delete remove --remove-data
```

`--remove-data` 删除的是：

```text
%USERPROFILE%\.codex-session-delete
```

不会主动删除 `~/.codex` 历史目录。

### 日志

```powershell
Get-Content "$env:USERPROFILE\.codex-session-delete\launcher.log"
Get-Content "$env:USERPROFILE\.codex-session-delete\watcher.log"
```

## macOS 使用方式

### 安装本地源码版本

在项目根目录执行：

```bash
python3 -m pip install -e .
```

### 默认安装

```bash
python3 -m codex_session_delete setup
```

默认会：

- 创建 `/Applications/Codex Mate.app`
- 注册用户级 LaunchAgent watcher
- 让原生 Codex 启动也能被 Codex Mate 接管

### 不安装 watcher

```bash
python3 -m codex_session_delete setup --no-watcher
```

### 启动

默认启动并同步历史：

```bash
python3 -m codex_session_delete launch
```

跳过历史同步启动：

```bash
python3 -m codex_session_delete launch --no-history-sync
```

### 查看历史状态

```bash
python3 -m codex_session_delete history-status --json
```

### 手动同步历史

```bash
python3 -m codex_session_delete history-sync --json
```

同步前会备份到：

```text
~/.codex/codex_mate_history_backups
```

### 恢复历史备份

恢复最新备份：

```bash
python3 -m codex_session_delete history-restore --json
```

恢复指定备份：

```bash
python3 -m codex_session_delete history-restore --backup ~/.codex/codex_mate_history_backups/state_5.sqlite.pre-sync.YYYYMMDD-HHMMSS.bak --json
```

### watcher 管理

安装 watcher：

```bash
python3 -m codex_session_delete watch-install
```

临时禁用：

```bash
python3 -m codex_session_delete watch-disable
```

重新启用：

```bash
python3 -m codex_session_delete watch-enable
```

移除：

```bash
python3 -m codex_session_delete watch-remove
```

LaunchAgent 路径：

```text
~/Library/LaunchAgents/dev.codexmate.watcher.plist
```

### 卸载

```bash
python3 -m codex_session_delete remove
```

删除 Codex Mate 自有数据：

```bash
python3 -m codex_session_delete remove --remove-data
```

`--remove-data` 删除的是：

```text
~/.codex-session-delete
```

不会主动删除 `~/.codex` 历史目录。

### 日志

```bash
cat ~/.codex-session-delete/launcher.log
cat ~/.codex-session-delete/watcher.log
cat ~/.codex-session-delete/watcher.launchd.log
cat ~/.codex-session-delete/watcher.launchd.err
```

## 推荐测试顺序

1. 安装源码版本。
2. 执行 `setup`，确认默认 watcher 安装正常。
3. 执行 `launch`，确认 Codex 可以打开，Codex Mate 菜单出现。
4. 检查项目侧栏历史是否仍显示。
5. 执行 `history-status --json`。
6. 执行 `history-sync --json`，确认同步后侧栏历史不消失。
7. 如历史曾经消失，执行 `history-restore --json` 恢复最近备份。
8. 测试原生 Codex 图标启动，确认 watcher 接管失败时不再反复关闭 Codex。
