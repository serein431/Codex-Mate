from __future__ import annotations

import shlex
import subprocess
import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def command_args(*args: str, prefer_pythonw: bool = False) -> list[str]:
    if is_frozen():
        return [sys.executable, *args]
    executable = sys.executable
    if prefer_pythonw and sys.platform == "win32":
        pythonw = Path(executable).with_name("pythonw.exe")
        if pythonw.exists():
            executable = str(pythonw)
    return [executable, "-m", "codex_mate", *args]


def command_string(*args: str, prefer_pythonw: bool = False) -> str:
    command = command_args(*args, prefer_pythonw=prefer_pythonw)
    if sys.platform == "win32":
        return subprocess.list2cmdline(command)
    return shlex.join(command)


def app_root(package_file: str | Path) -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(package_file).resolve().parent.parent
