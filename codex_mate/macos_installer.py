from __future__ import annotations

import plistlib
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from codex_mate.installers import InstallOptions


DEFAULT_INSTALL_ROOT = Path("/Applications")
APP_NAME = "Codex Mate.app"
BUNDLE_IDENTIFIER = "dev.codexmate"


def _app_root(options: "InstallOptions") -> Path:
    return (options.install_root or DEFAULT_INSTALL_ROOT) / APP_NAME


def remove_macos_app_shortcut(options: "InstallOptions") -> None:
    app = _app_root(options)
    if _is_owned_codex_mate_shortcut(app):
        shutil.rmtree(app)


def uninstall_macos_app(options: "InstallOptions") -> None:
    remove_macos_app_shortcut(options)


def _is_owned_codex_mate_shortcut(app: Path) -> bool:
    if not app.is_dir():
        return False
    plist = _read_info_plist(app / "Contents" / "Info.plist")
    if plist.get("CFBundleIdentifier") == BUNDLE_IDENTIFIER:
        return True
    return bool((app / "Contents" / "MacOS" / "CodexMate").is_file() and plist.get("CFBundleName") == "Codex Mate")


def _read_info_plist(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = plistlib.loads(path.read_bytes())
    except (OSError, plistlib.InvalidFileException):
        return {}
    return value if isinstance(value, dict) else {}
