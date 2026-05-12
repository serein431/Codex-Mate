from __future__ import annotations

import plistlib
import subprocess
import sys
from pathlib import Path

from codex_mate import runtime

WATCHER_RUN_NAME = "CodexMateWatcher"
WATCHER_RUN_KEY = "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run"
WATCHER_STARTUP_SHORTCUT_NAME = "CodexMateWatcher.lnk"
MACOS_LAUNCH_AGENT_LABEL = "dev.codexmate.watcher"
MACOS_LAUNCH_AGENT_NAME = f"{MACOS_LAUNCH_AGENT_LABEL}.plist"
WATCHER_MODULES = ("codex_mate", "_".join(("codex", "session", "delete")))


def data_root() -> Path:
    return Path.home() / ".codex-mate"


def _ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _watcher_command(debug_port: int) -> tuple[str, list[str], str, str]:
    command = runtime.command_args("watch", "--debug-port", str(debug_port), prefer_pythonw=True)
    exe = command[0]
    args = command[1:]
    arguments = subprocess.list2cmdline(args) if sys.platform == "win32" else " ".join(args)
    full = subprocess.list2cmdline(command) if sys.platform == "win32" else " ".join(command)
    return exe, args, arguments, full


def _module_regex(modules: tuple[str, ...]) -> str:
    return "(" + "|".join(modules) + ")"


def watcher_stdout_log_path() -> Path:
    return data_root() / "watcher.stdout.log"


def watcher_stderr_log_path() -> Path:
    return data_root() / "watcher.stderr.log"


def build_windows_watcher_install_script(debug_port: int) -> str:
    exe, _args, arguments, full_command = _watcher_command(debug_port)
    project_root = str(Path(__file__).resolve().parent.parent)
    run_key = WATCHER_RUN_KEY
    lock_name = f"watcher-{debug_port}.lock"
    return f"""
$ErrorActionPreference = 'Stop'
$Exe = {_ps_quote(exe)}
$Args = {_ps_quote(arguments)}
$RunFullCommand = {_ps_quote(full_command)}
$ProjectRoot = {_ps_quote(project_root)}
$ShortcutName = {_ps_quote(WATCHER_STARTUP_SHORTCUT_NAME)}
$WatcherModulePattern = {_ps_quote(_module_regex(WATCHER_MODULES))}
$DataRoot = Join-Path $env:USERPROFILE '.codex-mate'
$WatcherLockPath = Join-Path $DataRoot {_ps_quote(lock_name)}
if (Test-Path $WatcherLockPath) {{
    try {{
        $LockPidText = (Get-Content -Path $WatcherLockPath -Raw -ErrorAction Stop).Trim()
        if ($LockPidText -match '^\\d+$' -and [int]$LockPidText -ne $PID) {{
            Stop-Process -Id ([int]$LockPidText) -Force -ErrorAction SilentlyContinue
        }}
    }} catch {{}}
    Remove-Item $WatcherLockPath -Force -ErrorAction SilentlyContinue
}}
Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe' OR Name='CodexMate.exe'" | Where-Object {{ $_.CommandLine -match ($WatcherModulePattern + '\\s+(watch|launch)(\\s|$)') -or $_.CommandLine -match 'CodexMate(\\.exe)?\"?\\s+(watch|launch)(\\s|$)' }} | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }}
if (-not (Test-Path {_ps_quote(run_key)})) {{ New-Item -Path {_ps_quote(run_key)} -Force | Out-Null }}
Set-ItemProperty -Path {_ps_quote(run_key)} -Name '{WATCHER_RUN_NAME}' -Value $RunFullCommand
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
$runValue = (Get-ItemProperty -Path {_ps_quote(run_key)} -Name '{WATCHER_RUN_NAME}').'{WATCHER_RUN_NAME}'
Write-Output ("watch-install: HKCU Run = " + $runValue)
Write-Output ("watch-install: Startup shortcut = " + $ShortcutPath)
""".strip()


def build_windows_watcher_uninstall_script() -> str:
    return f"""
$WatcherModulePattern = {_ps_quote(_module_regex(WATCHER_MODULES))}
Remove-ItemProperty -Path '{WATCHER_RUN_KEY}' -Name '{WATCHER_RUN_NAME}' -ErrorAction SilentlyContinue | Out-Null
$Startup = [Environment]::GetFolderPath('Startup')
$ShortcutPath = Join-Path $Startup {_ps_quote(WATCHER_STARTUP_SHORTCUT_NAME)}
if (Test-Path $ShortcutPath) {{ Remove-Item $ShortcutPath -Force -ErrorAction SilentlyContinue }}
$DataRoot = Join-Path $env:USERPROFILE '.codex-mate'
Get-ChildItem -Path $DataRoot -Filter 'watcher-*.lock' -ErrorAction SilentlyContinue | ForEach-Object {{
    try {{
        $LockPidText = (Get-Content -Path $_.FullName -Raw -ErrorAction Stop).Trim()
        if ($LockPidText -match '^\\d+$' -and [int]$LockPidText -ne $PID) {{
            Stop-Process -Id ([int]$LockPidText) -Force -ErrorAction SilentlyContinue
        }}
    }} catch {{}}
    Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue
}}
Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe' OR Name='CodexMate.exe'" | Where-Object {{ $_.CommandLine -match ($WatcherModulePattern + '\\s+(watch|launch)(\\s|$)') -or $_.CommandLine -match 'CodexMate(\\.exe)?\"?\\s+(watch|launch)(\\s|$)' }} | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }}
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
    exe, args, _, _ = _watcher_command(debug_port)
    data_root().mkdir(parents=True, exist_ok=True)
    with watcher_stdout_log_path().open("ab") as stdout, watcher_stderr_log_path().open("ab") as stderr:
        subprocess.Popen(
            [exe, *args],
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            cwd=project_root(),
            env=runtime.independent_child_env(),
            close_fds=True,
            creationflags=(
                getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
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
    return runtime.app_root(__file__)


def build_macos_launch_agent_plist(python_executable: Path, debug_port: int, working_directory: Path | None = None) -> dict[str, object]:
    out_log = data_root() / "watcher.launchd.log"
    err_log = data_root() / "watcher.launchd.err"
    program_arguments = runtime.command_args("watch", "--debug-port", str(debug_port))
    program_arguments[0] = str(python_executable)
    return {
        "Label": MACOS_LAUNCH_AGENT_LABEL,
        "ProgramArguments": program_arguments,
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
    stop_macos_background_processes()
    subprocess.run(["launchctl", "load", "-w", str(path)], check=True)
    print(f"watch-install: LaunchAgent = {path}")


def uninstall_macos_watcher_autostart() -> None:
    path = macos_launch_agent_path()
    if path.exists():
        subprocess.run(["launchctl", "unload", str(path)], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        path.unlink()
    stop_macos_background_processes()


def stop_macos_background_processes() -> None:
    for module in WATCHER_MODULES:
        for command in ("watch", "launch"):
            subprocess.run(
                ["pkill", "-f", f"python.*-m {module} {command}"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    for command in ("watch", "launch"):
        subprocess.run(
            ["pkill", "-f", f"CodexMate {command}"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


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
