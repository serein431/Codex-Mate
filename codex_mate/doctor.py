from __future__ import annotations

import socket
import sys
from typing import Any

from codex_mate import __version__, app_paths, runtime, watcher


def port_listening(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def collect_status() -> dict[str, Any]:
    disabled_flag = watcher.watcher_disabled_flag()
    lock_path = watcher.watcher_lock_path(9229)
    cache_path = app_paths.codex_app_dir_cache_path()
    resolved = app_paths.resolve_codex_app_dir()
    return {
        "version": __version__,
        "platform": sys.platform,
        "frozen": runtime.is_frozen(),
        "launch_mode": "direct_launcher" if disabled_flag.exists() else "watcher_available",
        "watcher": {
            "enabled": not disabled_flag.exists(),
            "disabled_flag": str(disabled_flag),
            "lock_path": str(lock_path),
            "lock_exists": lock_path.exists(),
        },
        "ports": {
            "cdp_9229": port_listening(9229),
            "helper_57321": port_listening(57321),
        },
        "codex_app": {
            "cache_path": str(cache_path),
            "cache_exists": cache_path.exists(),
            "resolved_dir": resolved.as_posix() if resolved else "",
        },
    }
