from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from codex_mate import __version__
from codex_mate.runtime import command_string, is_frozen

if TYPE_CHECKING:
    from codex_mate.installers import InstallOptions


def _ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _launcher_command(options: "InstallOptions") -> str:
    if options.launcher_command:
        return options.launcher_command
    if is_frozen():
        return command_string("launch")
    return "python -m codex_mate launch"


def _install_root_expr(options: "InstallOptions") -> str:
    if options.install_root is not None:
        return _ps_quote(str(options.install_root))
    return "$([Environment]::GetFolderPath('Desktop'))"


def _project_root_expr() -> str:
    return _ps_quote(str(command_root()))


def command_root() -> Path:
    from codex_mate.runtime import app_root

    return app_root(__file__)


def _icon_path_expr() -> str:
    return _ps_quote(str(Path(__file__).resolve().parent / "assets" / "codex-mate.ico"))


def _split_launcher_command(command: str) -> tuple[str, str]:
    command = command.strip()
    if command.startswith('"'):
        end = command.find('"', 1)
        if end != -1:
            return command[1:end], command[end + 1 :].strip()
    parts = command.split(maxsplit=1)
    if not parts:
        return command, ""
    return parts[0], parts[1] if len(parts) > 1 else ""


def _uninstall_arguments(arguments: str) -> str:
    parts = arguments.split()
    if parts and parts[-1] == "launch":
        parts[-1] = "uninstall"
    elif not parts:
        parts = ["uninstall"]
    else:
        parts.append("uninstall")
    parts.append("--install-root")
    return subprocess.list2cmdline(parts)


def _uninstall_command_expr(target: str, arguments: str) -> str:
    target_expr = "$Python" if target == "python" else _ps_quote(target)
    uninstall_arguments = _uninstall_arguments(arguments)
    return f"'cmd.exe /c cd /d \"' + $ProjectRoot + '\" && \"' + {target_expr} + '\" {uninstall_arguments} \"' + $InstallRoot + '\"'"


def build_install_shortcut_script(options: "InstallOptions") -> str:
    root = _install_root_expr(options)
    project_root = _project_root_expr()
    icon_path = _icon_path_expr()
    target, arguments = _split_launcher_command(_launcher_command(options))
    target_expr = "$Pythonw" if target == "python" else _ps_quote(target)
    arguments_expr = _ps_quote(arguments)
    uninstall_command_expr = _uninstall_command_expr(target, arguments)
    return f"""
$InstallRoot = {root}
$ProjectRoot = {project_root}
$CodexMateIcon = {icon_path}
New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
$ShortcutPath = Join-Path $InstallRoot 'Codex Mate.lnk'
$Python = (Get-Command python).Source
$PythonwCandidate = Join-Path (Split-Path $Python -Parent) 'pythonw.exe'
$Pythonw = if (Test-Path $PythonwCandidate) {{ $PythonwCandidate }} else {{ $Python }}
$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = {target_expr}
$Shortcut.Arguments = {arguments_expr}
$Shortcut.WorkingDirectory = $ProjectRoot
$Shortcut.Description = 'Launch Codex with Codex Mate injection'
$Shortcut.IconLocation = $CodexMateIcon
$Shortcut.Save()
$LegacyUninstallKey = 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\Codex Mate'
if (Test-Path $LegacyUninstallKey) {{ Remove-Item $LegacyUninstallKey -Force }}
$UninstallKey = 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\CodexMate'
$UninstallCommand = {uninstall_command_expr}
New-Item -Path $UninstallKey -Force | Out-Null
Set-ItemProperty -Path $UninstallKey -Name DisplayName -Value 'Codex Mate'
Set-ItemProperty -Path $UninstallKey -Name DisplayVersion -Value '{__version__}'
Set-ItemProperty -Path $UninstallKey -Name Publisher -Value 'codex-mate'
Set-ItemProperty -Path $UninstallKey -Name DisplayIcon -Value $CodexMateIcon
Set-ItemProperty -Path $UninstallKey -Name InstallLocation -Value $ProjectRoot
Set-ItemProperty -Path $UninstallKey -Name UninstallString -Value $UninstallCommand
Set-ItemProperty -Path $UninstallKey -Name QuietUninstallString -Value $UninstallCommand
""".strip()


def build_uninstall_shortcut_script(options: "InstallOptions") -> str:
    root = _install_root_expr(options)
    return f"""
$InstallRoot = {root}
$ShortcutPath = Join-Path $InstallRoot 'Codex Mate.lnk'
if (Test-Path $ShortcutPath) {{ Remove-Item $ShortcutPath -Force }}
$LegacyUninstallKey = 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\Codex Mate'
if (Test-Path $LegacyUninstallKey) {{ Remove-Item $LegacyUninstallKey -Force }}
$UninstallKey = 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\CodexMate'
if (Test-Path $UninstallKey) {{ Remove-Item $UninstallKey -Force }}
""".strip()


def _run_powershell(script: str) -> None:
    subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script], check=True)


def install_windows_shortcuts(options: "InstallOptions") -> None:
    _run_powershell(build_install_shortcut_script(options))


def uninstall_windows_shortcuts(options: "InstallOptions") -> None:
    _run_powershell(build_uninstall_shortcut_script(options))
