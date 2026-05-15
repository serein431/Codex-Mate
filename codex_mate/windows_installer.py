from __future__ import annotations

import subprocess
import sys
import os
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


def install_root_path(options: "InstallOptions") -> Path:
    if options.install_root is not None:
        return options.install_root
    return Path.home() / "Desktop"


def _project_root_expr() -> str:
    return _ps_quote(str(command_root()))


def command_root() -> Path:
    from codex_mate.runtime import app_root

    return app_root(__file__)


def _icon_path_expr() -> str:
    return _ps_quote(str(Path(__file__).resolve().parent / "assets" / "codex-mate.ico"))


def local_icon_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    root = Path(local_app_data) / "CodexMate" if local_app_data else Path.home() / ".codex-mate"
    return root / "codex-mate.ico"


def ensure_local_icon() -> Path:
    source = Path(__file__).resolve().parent / "assets" / "codex-mate.ico"
    target = local_icon_path()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or source.stat().st_mtime > target.stat().st_mtime:
            target.write_bytes(source.read_bytes())
    except OSError:
        return source
    return target


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
    if "launch" in parts:
        launch_index = parts.index("launch")
        parts = parts[:launch_index] + ["uninstall"]
    elif parts and parts[-1] == "uninstall":
        pass
    elif not parts:
        parts = ["uninstall"]
    else:
        parts.append("uninstall")
    parts.append("--install-root")
    return subprocess.list2cmdline(parts)


def _uninstall_command_expr(target: str, arguments: str) -> str:
    target_expr = "$Python" if target == "python" else _ps_quote(target)
    uninstall_arguments = _uninstall_arguments(arguments)
    return f"'cmd.exe /c pushd \"' + $ProjectRoot + '\" && \"' + {target_expr} + '\" {uninstall_arguments} \"' + $InstallRoot + '\" & popd'"


def _uninstall_command(options: "InstallOptions") -> str:
    target, arguments = _split_launcher_command(_launcher_command(options))
    command = f'pushd "{command_root()}" && "{target}" {_uninstall_arguments(arguments)} "{install_root_path(options)}" & popd'
    return subprocess.list2cmdline(["cmd.exe", "/c", command])


def cmd_launcher_path(options: "InstallOptions") -> Path:
    return install_root_path(options) / "Codex Mate.cmd"


def write_cmd_launcher(options: "InstallOptions") -> Path:
    install_root = install_root_path(options)
    install_root.mkdir(parents=True, exist_ok=True)
    project_root = command_root()
    target, arguments = _split_launcher_command(_launcher_command(options))
    launcher_path = cmd_launcher_path(options)
    launcher_path.write_text(
        "\n".join(
            [
                "@echo off",
                f'pushd "{project_root}"',
                f'start "" "{target}" {arguments}'.rstrip(),
                "popd",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return launcher_path


def remove_cmd_launcher(options: "InstallOptions") -> None:
    try:
        cmd_launcher_path(options).unlink()
    except FileNotFoundError:
        pass


def register_windows_uninstall_entry(options: "InstallOptions", launcher_path: Path) -> None:
    try:
        import winreg
    except ImportError:
        return
    try:
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\CodexMate"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, "Codex Mate")
            winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, __version__)
            winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, "codex-mate")
            winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, str(command_root()))
            winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, str(ensure_local_icon()))
            uninstall_command = _uninstall_command(options)
            winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, uninstall_command)
            winreg.SetValueEx(key, "QuietUninstallString", 0, winreg.REG_SZ, uninstall_command)
    except OSError as exc:
        print(f"warning: unable to register uninstall entry: {exc}")


def unregister_windows_uninstall_entry() -> None:
    try:
        import winreg
    except ImportError:
        return
    for key_path in (
        r"Software\Microsoft\Windows\CurrentVersion\Uninstall\CodexMate",
        r"Software\Microsoft\Windows\CurrentVersion\Uninstall\Codex Mate",
    ):
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path)
        except FileNotFoundError:
            pass
        except OSError as exc:
            print(f"warning: unable to remove uninstall entry: {exc}")


def build_install_shortcut_script(options: "InstallOptions") -> str:
    root = _install_root_expr(options)
    project_root = _project_root_expr()
    source_icon_path = _icon_path_expr()
    target, arguments = _split_launcher_command(_launcher_command(options))
    target_expr = "$Pythonw" if target == "python" else _ps_quote(target)
    arguments_expr = _ps_quote(arguments)
    uninstall_command_expr = _uninstall_command_expr(target, arguments)
    return f"""
$InstallRoot = {root}
$ProjectRoot = {project_root}
$SourceIcon = {source_icon_path}
$DataRoot = if ($env:LOCALAPPDATA) {{ Join-Path $env:LOCALAPPDATA 'CodexMate' }} else {{ Join-Path $env:USERPROFILE '.codex-mate' }}
$CodexMateIcon = Join-Path $DataRoot 'codex-mate.ico'
New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
New-Item -ItemType Directory -Force -Path $DataRoot | Out-Null
if (Test-Path $SourceIcon) {{ Copy-Item -Path $SourceIcon -Destination $CodexMateIcon -Force }}
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
    try:
        _run_powershell(build_install_shortcut_script(options))
    except PermissionError as exc:
        launcher_path = write_cmd_launcher(options)
        register_windows_uninstall_entry(options, launcher_path)
        print(f"warning: PowerShell shortcut install was blocked: {exc}")
        print(f"fallback launcher created: {launcher_path}")


def uninstall_windows_shortcuts(options: "InstallOptions") -> None:
    try:
        _run_powershell(build_uninstall_shortcut_script(options))
    except PermissionError as exc:
        remove_cmd_launcher(options)
        unregister_windows_uninstall_entry()
        print(f"warning: PowerShell shortcut uninstall was blocked: {exc}")
