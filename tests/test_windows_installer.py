from pathlib import Path

from codex_mate.installers import InstallOptions
from codex_mate import __version__
from codex_mate import windows_installer
from codex_mate.windows_installer import build_install_shortcut_script, build_uninstall_shortcut_script


LEGACY_BRAND = "Codex" + "++"
LEGACY_OWNER = "Big" + "Pizza" + "V3"
LEGACY_PROJECT = "Codex" + "Plus" + "Plus"


def test_build_install_shortcut_script_contains_codex_mate_shortcuts(tmp_path):
    options = InstallOptions(install_root=tmp_path)

    script = build_install_shortcut_script(options)

    assert "Codex Mate.lnk" in script
    assert "codex-mate.ico" in script
    assert "-m codex_mate launch" in script
    assert "--no-history-sync" not in script
    assert "CreateShortcut" in script
    assert "TargetPath = $Pythonw" in script
    assert "pythonw.exe" in script
    assert "TargetPath = $Python\n" not in script
    assert "IconLocation" in script
    assert "-EncodedCommand" not in script
    assert "powershell.exe" not in script
    assert "WorkingDirectory = $ProjectRoot" in script
    assert "codex-mate.ico" in script
    assert "Codex.exe" not in script
    assert "IconLocation = $CodexMateIcon" in script
    assert "$Python,0" not in script
    assert str(Path.cwd()) in script
    assert "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\CodexMate" in script
    assert LEGACY_BRAND not in script
    assert LEGACY_OWNER not in script
    assert LEGACY_PROJECT not in script
    assert "DisplayName" in script
    assert "DisplayIcon" in script
    assert "UninstallString" in script
    assert "$UninstallCommand = 'cmd.exe /c cd /d \"' + $ProjectRoot + '\" && \"' + $Python + '\" -m codex_mate uninstall" in script
    assert "--install-root" in script
    assert "QuietUninstallString" in script
    assert f"DisplayVersion -Value '{__version__}'" in script


def test_build_uninstall_shortcut_script_removes_codex_mate_shortcuts(tmp_path):
    options = InstallOptions(install_root=tmp_path)

    script = build_uninstall_shortcut_script(options)

    assert "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\CodexMate" in script
    assert LEGACY_BRAND not in script
    assert LEGACY_OWNER not in script
    assert LEGACY_PROJECT not in script
    assert "Remove-Item" in script
    assert str(tmp_path) in script


def test_install_windows_shortcuts_falls_back_to_cmd_launcher_when_powershell_is_blocked(tmp_path, monkeypatch):
    monkeypatch.setattr(windows_installer, "_run_powershell", lambda script: (_ for _ in ()).throw(PermissionError("Access is denied")))
    monkeypatch.setattr(windows_installer, "command_root", lambda: tmp_path / "project")
    monkeypatch.setattr(windows_installer, "register_windows_uninstall_entry", lambda options, launcher_path: None)

    windows_installer.install_windows_shortcuts(InstallOptions(install_root=tmp_path, launcher_command='"C:\\Tools\\CodexMate.exe" launch'))

    launcher = tmp_path / "Codex Mate.cmd"
    assert launcher.exists()
    text = launcher.read_text(encoding="utf-8")
    assert 'cd /d "' in text
    assert 'start "" "C:\\Tools\\CodexMate.exe" launch' in text


def test_uninstall_windows_shortcuts_removes_cmd_fallback_when_powershell_is_blocked(tmp_path, monkeypatch):
    launcher = tmp_path / "Codex Mate.cmd"
    launcher.write_text("@echo off\n", encoding="utf-8")
    monkeypatch.setattr(windows_installer, "_run_powershell", lambda script: (_ for _ in ()).throw(PermissionError("Access is denied")))
    monkeypatch.setattr(windows_installer, "unregister_windows_uninstall_entry", lambda: None)

    windows_installer.uninstall_windows_shortcuts(InstallOptions(install_root=tmp_path))

    assert not launcher.exists()
