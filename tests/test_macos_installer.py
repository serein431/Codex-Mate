import plistlib

from codex_mate.installers import InstallOptions
from codex_mate.macos_installer import remove_macos_app_shortcut, uninstall_macos_app


def write_app_bundle(root, bundle_identifier="dev.codexmate", bundle_name="Codex Mate"):
    app = root / "Codex Mate.app"
    contents = app / "Contents"
    macos = contents / "MacOS"
    macos.mkdir(parents=True)
    (contents / "Info.plist").write_bytes(
        plistlib.dumps({"CFBundleIdentifier": bundle_identifier, "CFBundleName": bundle_name})
    )
    (macos / "CodexMate").write_text("#!/bin/sh\n", encoding="utf-8")
    return app


def test_remove_macos_app_shortcut_removes_owned_legacy_bundle(tmp_path):
    app = write_app_bundle(tmp_path)

    remove_macos_app_shortcut(InstallOptions(install_root=tmp_path))

    assert not app.exists()


def test_remove_macos_app_shortcut_leaves_unrelated_bundle(tmp_path):
    app = write_app_bundle(tmp_path, bundle_identifier="com.example.other", bundle_name="Other App")

    remove_macos_app_shortcut(InstallOptions(install_root=tmp_path))

    assert app.exists()


def test_uninstall_macos_app_removes_owned_legacy_bundle(tmp_path):
    app = write_app_bundle(tmp_path)

    uninstall_macos_app(InstallOptions(install_root=tmp_path))

    assert not app.exists()
