from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import traceback
from pathlib import Path

from codex_mate import codex_storage
from codex_mate.helper_server import HelperServer
from codex_mate.installers import InstallOptions, install_codex_mate, uninstall_codex_mate
from codex_mate.launcher import launch_and_inject, shutdown_helper
from codex_mate import autostart
from codex_mate import diagnostics
from codex_mate import doctor
from codex_mate import history_sync
from codex_mate import native_features
from codex_mate import updater
from codex_mate import watcher


def add_launch_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--app-dir", type=Path, default=None)
    parser.add_argument("--db", type=Path, default=None, help="SQLite database path for local deletion fallback")
    parser.add_argument("--backup-dir", type=Path, default=Path.home() / ".codex-mate" / "backups")
    parser.add_argument("--debug-port", type=int, default=9229)
    parser.add_argument("--helper-port", type=int, default=57321)
    parser.add_argument("--no-history-sync", action="store_true", help="Skip Codex local history provider/model sync before launch")
    parser.add_argument("--no-native-feature-sync", action="store_true", help="Skip enabling native Codex mobile/remote feature flags before launch")


def add_history_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--codex-home", type=Path, default=None, help="Codex data directory; defaults to ~/.codex")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")


def add_provider_mode_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--codex-home", type=Path, default=None, help="Codex data directory; defaults to ~/.codex")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")


def add_provider_mode_profile_arguments(parser: argparse.ArgumentParser) -> None:
    add_provider_mode_common_arguments(parser)
    parser.add_argument("--provider", required=True, help="Provider name to write into config.toml")
    parser.add_argument("--base-url", required=True, help="OpenAI-compatible API base URL")
    parser.add_argument("--api-key", required=True, help="API key for the provider")
    parser.add_argument("--model", default="", help="Optional model name to write into config.toml")
    parser.add_argument("--wire-api", default="responses", choices=["responses", "chat"], help="Codex provider wire API")


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

    doctor_parser = subparsers.add_parser("doctor", help="Show Codex Mate startup and injection diagnostics")
    doctor_parser.add_argument("--json", action="store_true", help="Emit JSON output")

    logs_parser = subparsers.add_parser("logs", help="Export a redacted diagnostic log bundle")
    logs_parser.add_argument("--output", type=Path, default=None, help="Output zip path; defaults to ~/.codex-mate/diagnostics")

    history_status_parser = subparsers.add_parser("history-status", help="Show local history sync status")
    add_history_arguments(history_status_parser)
    history_sync_parser = subparsers.add_parser("history-sync", help="Sync local history to the current provider/model")
    add_history_arguments(history_sync_parser)
    provider_sync_parser = subparsers.add_parser("provider-sync", help="Safely sync local history visibility to the current provider")
    add_history_arguments(provider_sync_parser)

    provider_mode_parser = subparsers.add_parser("provider-mode", help="Inspect or switch Codex provider auth mode")
    provider_mode_subparsers = provider_mode_parser.add_subparsers(dest="provider_mode")
    provider_mode_status_parser = provider_mode_subparsers.add_parser("status", help="Show current provider auth mode")
    add_provider_mode_common_arguments(provider_mode_status_parser)
    provider_mode_official_parser = provider_mode_subparsers.add_parser("official", help="Use official ChatGPT login without API key files")
    add_provider_mode_common_arguments(provider_mode_official_parser)
    provider_mode_mixed_parser = provider_mode_subparsers.add_parser("mixed-api", help="Keep ChatGPT login and put the API key in the provider config")
    add_provider_mode_profile_arguments(provider_mode_mixed_parser)
    provider_mode_pure_parser = provider_mode_subparsers.add_parser("pure-api", help="Use API key auth.json plus provider config")
    add_provider_mode_profile_arguments(provider_mode_pure_parser)

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


def wait_for_visible_codex_processes() -> bool:
    pids = watcher.find_codex_processes()
    if not pids:
        return False
    while pids:
        time.sleep(2)
        pids = watcher.find_codex_processes()
    return True


def wait_for_shutdown(server: HelperServer, codex_proc) -> None:
    try:
        if isinstance(codex_proc, int):
            if not wait_for_visible_codex_processes():
                wait_for_windows_process_id(codex_proc)
        elif codex_proc is None and sys.platform == "darwin":
            wait_for_visible_codex_processes()
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
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def helper_port_available(port: int) -> bool:
    if port == 0:
        return True
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            if sys.platform == "win32" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            probe.bind(("127.0.0.1", port))
            return True
    except OSError:
        return False


def stop_existing_windows_launchers_if_needed(helper_port: int) -> None:
    if sys.platform == "win32" and not helper_port_available(helper_port):
        stop_existing_windows_launchers()


def run_launch(args: argparse.Namespace) -> int:
    args.db = resolve_launch_db_path(args)
    stop_existing_windows_launchers_if_needed(args.helper_port)
    if not args.no_native_feature_sync:
        sync_native_features_before_launch(args)
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


def resolve_launch_db_path(args: argparse.Namespace) -> Path | None:
    if getattr(args, "db", None) is not None:
        return args.db
    return codex_storage.primary_thread_db_path()


def sync_native_features_before_launch(args: argparse.Namespace) -> None:
    try:
        codex_home = codex_storage.codex_home_for_db_path(args.db) if getattr(args, "db", None) else None
        result = native_features.ensure_remote_feature_flags(codex_home)
    except Exception as exc:
        append_launch_warning("native feature sync failed before launch: " + str(exc))
        print(f"Native feature sync skipped: {exc}")
        return
    if result.get("status") != "updated":
        return
    updated = ", ".join(str(item) for item in result.get("updated_features", []))
    print(f"Enabled native Codex remote feature flags: {updated}.")


def sync_history_before_launch(args: argparse.Namespace) -> None:
    try:
        codex_home = codex_storage.codex_home_for_db_path(args.db) if getattr(args, "db", None) else None
        result = history_sync.sync_history_visibility_if_ready(history_sync.resolve_paths(codex_home))
    except Exception as exc:
        append_launch_warning("history visibility sync failed before launch: " + str(exc))
        print(f"History visibility sync skipped: {exc}")
        return
    if result.get("skipped"):
        return
    changed = int(result.get("updated_database_rows", 0)) + int(result.get("updated_session_files", 0))
    if changed:
        print(
            "History visibility synced to current provider "
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


def run_provider_sync(args: argparse.Namespace) -> int:
    payload = history_sync.sync_history_visibility_if_ready(history_sync.resolve_paths(args.codex_home))
    print_payload(payload, args.json)
    return 0


def run_provider_mode(args: argparse.Namespace) -> int:
    if args.provider_mode == "status":
        payload = native_features.provider_mode_status(args.codex_home)
    elif args.provider_mode == "official":
        payload = native_features.apply_provider_mode(args.codex_home, mode="official")
    elif args.provider_mode in {"mixed-api", "pure-api"}:
        payload = native_features.apply_provider_mode(
            args.codex_home,
            mode=args.provider_mode,
            provider=args.provider,
            base_url=args.base_url,
            api_key=args.api_key,
            model=args.model,
            wire_api=args.wire_api,
        )
    else:
        raise SystemExit("provider-mode requires one of: status, official, mixed-api, pure-api")
    print_payload(payload, args.json)
    return 0


def run_logs(args: argparse.Namespace) -> int:
    archive = diagnostics.collect_diagnostics(output_path=args.output)
    print(f"诊断日志已导出: {archive}")
    return 0


def run_doctor(args: argparse.Namespace) -> int:
    payload = doctor.collect_status()
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    print_payload(payload, False)
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
        watcher.enable_watcher()
        autostart.install_watcher_autostart(args.debug_port)
        return 0
    if args.command == "watch-remove":
        autostart.uninstall_watcher_autostart()
        watcher.disable_watcher()
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
    if args.command == "provider-sync":
        return run_provider_sync(args)
    if args.command == "provider-mode":
        return run_provider_mode(args)
    if args.command == "logs":
        return run_logs(args)
    if args.command == "doctor":
        return run_doctor(args)
    return run_launch(args)


if __name__ == "__main__":
    raise SystemExit(main())
