from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

from codex_mate.helper_server import HelperServer
from codex_mate.installers import InstallOptions, install_codex_mate, uninstall_codex_mate
from codex_mate.launcher import launch_and_inject, shutdown_helper
from codex_mate import autostart
from codex_mate import history_sync
from codex_mate import updater
from codex_mate import watcher


def add_launch_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--app-dir", type=Path, default=None)
    parser.add_argument("--db", type=Path, default=Path.home() / ".codex" / "state_5.sqlite", help="SQLite database path for local deletion fallback")
    parser.add_argument("--backup-dir", type=Path, default=Path.home() / ".codex-mate" / "backups")
    parser.add_argument("--debug-port", type=int, default=9229)
    parser.add_argument("--helper-port", type=int, default=57321)
    parser.add_argument("--no-history-sync", action="store_true", help="Skip Codex local history provider/model sync before launch")


def add_history_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--codex-home", type=Path, default=None, help="Codex data directory; defaults to ~/.codex")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Launch and install Codex Mate for Codex App")
    subparsers = parser.add_subparsers(dest="command")

    launch_parser = subparsers.add_parser("launch", help="Launch Codex with Codex Mate injection")
    add_launch_arguments(launch_parser)

    install_parser = subparsers.add_parser("install", help="Install the Codex Mate launcher entry point")
    install_parser.add_argument("--install-root", type=Path, default=None)
    install_parser.add_argument("--launcher-command", default=None)

    setup_parser = subparsers.add_parser("setup", help="Install Codex Mate with defaults")
    setup_parser.add_argument("--install-root", type=Path, default=None)

    uninstall_parser = subparsers.add_parser("uninstall", help="Remove the Codex Mate launcher entry point")
    uninstall_parser.add_argument("--install-root", type=Path, default=None)
    uninstall_parser.add_argument("--remove-data", action="store_true")

    remove_parser = subparsers.add_parser("remove", help="Remove Codex Mate with defaults")
    remove_parser.add_argument("--install-root", type=Path, default=None)
    remove_parser.add_argument("--remove-data", action="store_true")

    watch_parser = subparsers.add_parser("watch", help="Run the Codex watcher loop (auto-reinject when Codex is launched normally)")
    watch_parser.add_argument("--debug-port", type=int, default=9229)

    watch_install_parser = subparsers.add_parser("watch-install", help="Register the watcher to run at Windows logon")
    watch_install_parser.add_argument("--debug-port", type=int, default=9229)

    subparsers.add_parser("watch-remove", help="Unregister the watcher logon task")

    subparsers.add_parser("watch-enable", help="Re-enable the watcher loop after it was disabled")
    subparsers.add_parser("watch-disable", help="Disable the watcher loop without removing the logon task")

    subparsers.add_parser("check-update", help="Check GitHub Releases for a newer Codex Mate version")
    subparsers.add_parser("update", help="Update Codex Mate from the latest GitHub Release")

    history_status_parser = subparsers.add_parser("history-status", help="Show local history sync status")
    add_history_arguments(history_status_parser)
    history_sync_parser = subparsers.add_parser("history-sync", help="Sync local history to the current provider/model")
    add_history_arguments(history_sync_parser)

    add_launch_arguments(parser)
    return parser




def launch_log_path() -> Path:
    return Path.home() / ".codex-mate" / "launcher.log"


def log_launch_failure(exc: BaseException) -> None:
    path = launch_log_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)), encoding="utf-8")
    except OSError:
        pass


def append_launch_warning(message: str) -> None:
    path = launch_log_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(message.rstrip() + "\n")
    except OSError:
        pass


def wait_for_windows_process_id(process_id: int) -> None:
    if sys.platform != "win32":
        return
    import ctypes

    synchronize = 0x00100000
    infinite = 0xFFFFFFFF
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    kernel32.WaitForSingleObject.restype = ctypes.c_ulong
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int

    handle = kernel32.OpenProcess(synchronize, False, process_id)
    if not handle:
        return
    try:
        kernel32.WaitForSingleObject(handle, infinite)
    finally:
        kernel32.CloseHandle(handle)


def wait_for_shutdown(server: HelperServer, codex_proc) -> None:
    try:
        if isinstance(codex_proc, int):
            wait_for_windows_process_id(codex_proc)
        elif codex_proc is None and sys.platform == "darwin":
            while True:
                if not watcher.find_codex_processes():
                    break
                time.sleep(2)
        elif codex_proc is not None:
            codex_proc.wait()
    except KeyboardInterrupt:
        pass
    finally:
        shutdown_helper(server)


def stop_existing_windows_launchers() -> None:
    if sys.platform != "win32":
        return
    current_pid = os.getpid()
    modules = ("codex_mate", "_".join(("codex", "session", "delete")))
    module_pattern = "(" + "|".join(modules) + ")"
    script = (
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.ProcessId -ne $env:CODEX_MATE_PID -and "
        f"($_.CommandLine -match 'pythonw?(.exe)?\"?\\s+-m\\s+{module_pattern}\\s+launch(\\s|$)' -or "
        "$_.CommandLine -match 'CodexMate(\\.exe)?\"?\\s+launch(\\s|$)') } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
    )
    env = {**os.environ, "CODEX_MATE_PID": str(current_pid)}
    subprocess.run(["powershell", "-NoProfile", "-Command", script], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)


def run_launch(args: argparse.Namespace) -> int:
    stop_existing_windows_launchers()
    if not args.no_history_sync:
        sync_history_before_launch(args)
    maybe_print_update_notice()
    try:
        server, codex_proc = launch_and_inject(args.app_dir, args.db, args.backup_dir, args.debug_port, args.helper_port)
    except Exception as exc:
        log_launch_failure(exc)
        raise
    print(f"Codex Mate helper running on http://127.0.0.1:{server.port}")
    print("Keep this terminal open while using the delete buttons. Press Ctrl+C to stop.")
    wait_for_shutdown(server, codex_proc)
    return 0


def sync_history_before_launch(args: argparse.Namespace) -> None:
    try:
        codex_home = args.db.parent if getattr(args, "db", None) else None
        result = history_sync.sync_history_if_ready(history_sync.resolve_paths(codex_home))
    except Exception as exc:
        append_launch_warning("history sync failed before launch: " + str(exc))
        print(f"History sync skipped: {exc}")
        return
    if result.get("skipped"):
        return
    changed = int(result.get("updated_database_rows", 0)) + int(result.get("updated_session_files", 0))
    if changed:
        print(
            "History synced to current provider/model "
            f"(database rows={result.get('updated_database_rows')}, session files={result.get('updated_session_files')})."
        )


def print_payload(payload: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    print(payload)


def print_release_notice(release: updater.Release) -> None:
    print(f"发现新版本 {release.version}: {release.url}")
    asset_name = getattr(release, "asset_name", None)
    if asset_name:
        print(f"更新包: {asset_name}")
    print("运行 `python -m codex_mate update` 可从 GitHub Release 更新。")


def maybe_print_update_notice() -> None:
    try:
        release = updater.check_for_update()
    except Exception:
        return
    if release is not None:
        print_release_notice(release)


def run_check_update() -> int:
    if updater.is_source_tree_mode():
        print("检测到当前正在从源码目录运行 Codex Mate。源码模式不检测 Release 版本；运行 `python -m codex_mate update` 可迁移到 Release 安装。")
        return 0
    release = updater.check_for_update()
    if release is None:
        print("当前已是最新版本。")
        return 0
    print_release_notice(release)
    return 0


def run_update() -> int:
    if updater.is_source_tree_mode():
        print("检测到当前正在从源码目录运行 Codex Mate，将迁移到 Release 安装。")
        release = updater.fetch_latest_release()
    else:
        release = updater.check_for_update()
        if release is None:
            print("当前已是最新版本。")
            return 0
    print_release_notice(release)
    updater.perform_update(release)
    print("更新完成。")
    return 0


def run_history_status(args: argparse.Namespace) -> int:
    payload = history_sync.status(history_sync.resolve_paths(args.codex_home))
    print_payload(payload, args.json)
    return 0


def run_history_sync(args: argparse.Namespace) -> int:
    payload = history_sync.sync_history_to_current_profile(history_sync.resolve_paths(args.codex_home))
    print_payload(payload, args.json)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command in {"install", "setup"}:
        install_codex_mate(InstallOptions(install_root=args.install_root, launcher_command=getattr(args, "launcher_command", None)))
        return 0
    if args.command in {"uninstall", "remove"}:
        uninstall_codex_mate(InstallOptions(install_root=args.install_root, remove_data=args.remove_data))
        return 0
    if args.command == "watch":
        return watcher.watch_loop(debug_port=args.debug_port)
    if args.command == "watch-install":
        autostart.install_watcher_autostart(args.debug_port)
        return 0
    if args.command == "watch-remove":
        autostart.uninstall_watcher_autostart()
        return 0
    if args.command == "watch-enable":
        watcher.enable_watcher()
        return 0
    if args.command == "watch-disable":
        watcher.disable_watcher()
        return 0
    if args.command == "check-update":
        return run_check_update()
    if args.command == "update":
        return run_update()
    if args.command == "history-status":
        return run_history_status(args)
    if args.command == "history-sync":
        return run_history_sync(args)
    return run_launch(args)


if __name__ == "__main__":
    raise SystemExit(main())
