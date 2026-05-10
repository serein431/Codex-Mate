from __future__ import annotations

import plistlib
import subprocess
import sys
from pathlib import Path


WATCHER_RUN_NAME = "CodexMateWatcher"
WATCHER_RUN_KEY = "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run"
WATCHER_STARTUP_SHORTCUT_NAME = "CodexMateWatcher.lnk"
MACOS_LAUNCH_AGENT_LABEL = "dev.codexmate.watcher"
MACOS_LAUNCH_AGENT_NAME = f"{MACOS_LAUNCH_AGENT_LABEL}.plist"


def data_root() -> Path:
    return Path.home() / ".codex-session-delete"


def _ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _watcher_command(debug_port: int) -> tuple[str, str, str]:
    python = sys.executable
    pythonw = Path(python).with_name("pythonw.exe")
    exe = str(pythonw if pythonw.exists() else python)
    arguments = f"-m codex_session_delete watch --debug-port {debug_port}"
    full = f'"{exe}" {arguments}'
    return exe, arguments, full


def build_windows_watcher_install_script(debug_port: int) -> str:
    exe, arguments, full_command = _watcher_command(debug_port)
    project_root = str(Path(__file__).resolve().parent.parent)
    return f"""
$ErrorActionPreference = 'Stop'
$Exe = {_ps_quote(exe)}
$Args = {_ps_quote(arguments)}
$RunFullCommand = {_ps_quote(full_command)}
$ProjectRoot = {_ps_quote(project_root)}
$ShortcutName = {_ps_quote(WATCHER_STARTUP_SHORTCUT_NAME)}
New-Item -Path '{WATCHER_RUN_KEY}' -Force | Out-Null
Set-ItemProperty -Path '{WATCHER_RUN_KEY}' -Name '{WATCHER_RUN_NAME}' -Value $RunFullCommand
$Startup = [Environment]::GetFolderPath('Startup')
New-Item -ItemType Directory -Force -Path $Startup | Out-Null
$Shell = New-Object -ComObject WScript.Shell
$ShortcutPath = Join-Path $Startup $ShortcutName
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $Exe
$Shortcut.Arguments = $Args
$Shortcut.WorkingDirectory = $ProjectRoot
$Shortcut.WindowStyle = 7
$Shortcut.Description = 'Codex Mate watcher (auto-inject Codex on start)'
$Shortcut.Save()
$runValue = (Get-ItemProperty -Path '{WATCHER_RUN_KEY}' -Name '{WATCHER_RUN_NAME}').'{WATCHER_RUN_NAME}'
Write-Output ("watch-install: HKCU Run = " + $runValue)
Write-Output ("watch-install: Startup shortcut = " + $ShortcutPath)
""".strip()


def build_windows_watcher_uninstall_script() -> str:
    return f"""
Remove-ItemProperty -Path '{WATCHER_RUN_KEY}' -Name '{WATCHER_RUN_NAME}' -ErrorAction SilentlyContinue | Out-Null
$Startup = [Environment]::GetFolderPath('Startup')
$ShortcutPath = Join-Path $Startup {_ps_quote(WATCHER_STARTUP_SHORTCUT_NAME)}
if (Test-Path $ShortcutPath) {{ Remove-Item $ShortcutPath -Force -ErrorAction SilentlyContinue }}
Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" | Where-Object {{ $_.CommandLine -match 'codex_session_delete\\s+watch' }} | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }}
""".strip()


def install_windows_watcher_autostart(debug_port: int) -> None:
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", build_windows_watcher_install_script(debug_port)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.stdout:
        print(result.stdout.strip())
    exe, _, _ = _watcher_command(debug_port)
    subprocess.Popen(
        [exe, "-m", "codex_session_delete", "watch", "--debug-port", str(debug_port)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        creationflags=(
            subprocess.CREATE_NEW_PROCESS_GROUP
            | getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        ),
    )
    print("watch-install: watcher process spawned")


def uninstall_windows_watcher_autostart() -> None:
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", build_windows_watcher_uninstall_script()],
        check=False,
    )


def macos_launch_agent_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / MACOS_LAUNCH_AGENT_NAME


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def build_macos_launch_agent_plist(python_executable: Path, debug_port: int, working_directory: Path | None = None) -> dict[str, object]:
    out_log = data_root() / "watcher.launchd.log"
    err_log = data_root() / "watcher.launchd.err"
    return {
        "Label": MACOS_LAUNCH_AGENT_LABEL,
        "ProgramArguments": [
            str(python_executable),
            "-m",
            "codex_session_delete",
            "watch",
            "--debug-port",
            str(debug_port),
        ],
        "RunAtLoad": True,
        "KeepAlive": True,
        "WorkingDirectory": str(working_directory or project_root()),
        "StandardOutPath": str(out_log),
        "StandardErrorPath": str(err_log),
    }


def write_macos_launch_agent(debug_port: int) -> Path:
    path = macos_launch_agent_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data_root().mkdir(parents=True, exist_ok=True)
    plist = build_macos_launch_agent_plist(Path(sys.executable), debug_port)
    path.write_bytes(plistlib.dumps(plist))
    return path


def install_macos_watcher_autostart(debug_port: int) -> None:
    path = write_macos_launch_agent(debug_port)
    subprocess.run(["launchctl", "unload", str(path)], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["launchctl", "load", "-w", str(path)], check=True)
    print(f"watch-install: LaunchAgent = {path}")


def uninstall_macos_watcher_autostart() -> None:
    path = macos_launch_agent_path()
    if path.exists():
        subprocess.run(["launchctl", "unload", str(path)], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        path.unlink()


def install_watcher_autostart(debug_port: int) -> None:
    if sys.platform == "win32":
        install_windows_watcher_autostart(debug_port)
        return
    if sys.platform == "darwin":
        install_macos_watcher_autostart(debug_port)
        return
    raise RuntimeError(f"watch-install is not supported on {sys.platform}")


def uninstall_watcher_autostart() -> None:
    if sys.platform == "win32":
        uninstall_windows_watcher_autostart()
        return
    if sys.platform == "darwin":
        uninstall_macos_watcher_autostart()
