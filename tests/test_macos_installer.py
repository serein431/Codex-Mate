import os
import plistlib
import stat

from codex_mate.installers import InstallOptions
from codex_mate import __version__
from codex_mate.macos_installer import install_macos_app, uninstall_macos_app


def test_install_macos_app_creates_app_bundle(tmp_path):
    options = InstallOptions(install_root=tmp_path, launcher_command="python -m codex_mate launch")

    install_macos_app(options)

    app = tmp_path / "Codex Mate.app"
    plist_path = app / "Contents" / "Info.plist"
    executable = app / "Contents" / "MacOS" / "CodexMate"
    assert plist_path.exists()
    assert executable.exists()
    if os.name == "posix":
        assert executable.stat().st_mode & stat.S_IXUSR

    plist = plistlib.loads(plist_path.read_bytes())
    assert plist["CFBundleName"] == "Codex Mate"
    assert plist["CFBundleExecutable"] == "CodexMate"
    assert plist["CFBundleIdentifier"] == "dev.codexmate"
    assert plist["CFBundleIconFile"] == "codex-mate.png"
    assert plist["CFBundleVersion"] == __version__
    assert plist["CFBundleShortVersionString"] == __version__
    assert (app / "Contents" / "Resources" / "codex-mate.png").exists()

    script = executable.read_text(encoding="utf-8")
    assert "python -m codex_mate launch" in script
    assert "exec" in script


def test_uninstall_macos_app_removes_app_bundle(tmp_path):
    options = InstallOptions(install_root=tmp_path, launcher_command="python -m codex_mate launch")
    install_macos_app(options)

    uninstall_macos_app(InstallOptions(install_root=tmp_path))

    assert not (tmp_path / "Codex Mate.app").exists()
