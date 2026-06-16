from __future__ import annotations

import ctypes
import socket
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from codex_mate.app_paths import resolve_codex_app_dir
from codex_mate.api_adapter import ApiAdapter, UnavailableApiAdapter
from codex_mate.backup_store import BackupStore
from codex_mate.cdp import inject_file, list_targets
from codex_mate.conversation_timeline import ConversationTimelineService
from codex_mate.helper_server import HelperServer
from codex_mate.markdown_export import MarkdownExportService
from codex_mate.models import DeleteResult, DeleteStatus, SessionRef
from codex_mate.storage_adapter import SQLiteStorageAdapter
from codex_mate import __version__, native_features, runtime, updater


class ApiFirstDeleteService:
    def __init__(self, api_adapter: ApiAdapter, db_path: Path | None, backup_dir: Path):
        self.api_adapter = api_adapter
        self.local_adapter = SQLiteStorageAdapter(db_path, BackupStore(backup_dir)) if db_path else None
        self.markdown_exporter = MarkdownExportService(db_path)
        self.timeline = ConversationTimelineService(db_path)
        self._update_lock = threading.Lock()

    def delete(self, session: SessionRef) -> DeleteResult:
        api_result = self.api_adapter.delete(session)
        if api_result is not None:
            return api_result
        if self.local_adapter is None:
            return DeleteResult(DeleteStatus.FAILED, session.session_id, "No confirmed server API or local database configured")
        return self.local_adapter.delete_local(session)

    def undo(self, token: str) -> DeleteResult:
        if self.local_adapter is None:
            return DeleteResult(DeleteStatus.FAILED, "", "No local backup adapter configured", undo_token=token)
        return self.local_adapter.undo(token)

    def find_archived_thread_by_title(self, title: str) -> SessionRef | None:
        if self.local_adapter is None:
            return None
        return self.local_adapter.find_archived_thread_by_title(title)

    def check_update(self) -> dict[str, object]:
        if runtime.is_frozen():
            release = updater.fetch_latest_release()
            if not updater.is_newer_version(release.version, __version__):
                return {
                    "status": "up_to_date",
                    "current_version": __version__,
                    "latest_version": release.version,
                    "release_url": release.url,
                    "asset_name": release.asset_name or "",
                    "can_update": False,
                    "message": "当前已是最新版本。",
                }
            return self._release_payload(
                "manual_required",
                release,
                "打包版需要下载安装包更新，请打开 Release 下载最新平台包。",
                can_update=False,
            )
        if updater.is_source_tree_mode():
            release = updater.fetch_latest_release()
            if updater.is_newer_version(__version__, release.version):
                return {
                    "status": "up_to_date",
                    "current_version": __version__,
                    "latest_version": release.version,
                    "release_url": release.url,
                    "asset_name": release.asset_name or "",
                    "can_update": False,
                    "message": "当前源码版本不低于最新 Release。",
                }
            return self._release_payload(
                "source_tree",
                release,
                "当前从源码目录运行，可一键迁移到最新 Release 安装。",
                can_update=True,
            )
        release = updater.check_for_update()
        if release is None:
            return {
                "status": "up_to_date",
                "current_version": __version__,
                "latest_version": __version__,
                "can_update": False,
                "message": "当前已是最新版本。",
            }
        return self._release_payload("available", release, f"发现新版本 {release.version}。", can_update=True)

    def update(self) -> dict[str, object]:
        if not self._update_lock.acquire(blocking=False):
            return {
                "status": "updating",
                "current_version": __version__,
                "latest_version": __version__,
                "can_update": False,
                "message": "已有更新任务正在进行，请等待当前更新完成。",
            }
        if runtime.is_frozen():
            try:
                release = updater.fetch_latest_release()
                return self._release_payload(
                    "manual_required",
                    release,
                    "打包版需要下载安装包更新，请打开 Release 下载最新平台包。",
                    can_update=False,
                )
            finally:
                self._update_lock.release()
        try:
            if updater.is_source_tree_mode():
                release = updater.fetch_latest_release()
            else:
                release = updater.check_for_update()
                if release is None:
                    return {
                        "status": "up_to_date",
                        "current_version": __version__,
                        "latest_version": __version__,
                        "can_update": False,
                        "message": "当前已是最新版本。",
                    }
            updater.perform_update(release)
            return self._release_payload("updated", release, f"已更新到 {release.version}，重启 Codex 后生效。", can_update=False)
        finally:
            self._update_lock.release()

    def export_markdown(self, session: SessionRef) -> dict[str, object]:
        return self.markdown_exporter.export(session).to_dict()

    def conversation_timeline(self, session: SessionRef) -> dict[str, object]:
        return self.timeline.timeline(session)

    def backend_status(self) -> dict[str, object]:
        return {"status": "ok", "message": "后端已连接", "version": __version__}

    def auth_enhancement_mode_status(self) -> dict[str, object]:
        return native_features.auth_enhancement_mode_status()

    def set_auth_enhancement_mode(self, mode: str) -> dict[str, object]:
        return native_features.set_auth_enhancement_mode(mode=mode)

    def provider_profile_status(self) -> dict[str, object]:
        return native_features.provider_profile_status()

    def apply_provider_profile(self, profile: dict[str, object]) -> dict[str, object]:
        return native_features.apply_provider_profile(profile=profile)

    def cc_switch_providers(self) -> dict[str, object]:
        return native_features.cc_switch_providers_status()

    def apply_cc_switch_provider(self, source_id: str) -> dict[str, object]:
        return native_features.apply_cc_switch_provider(source_id=source_id)

    def move_thread_workspace(self, session: SessionRef, target_cwd: str) -> dict[str, object]:
        if self.local_adapter is None:
            return {"status": "failed", "session_id": session.session_id, "message": "No local database configured"}
        return self.local_adapter.move_codex_thread_workspace(session, target_cwd)

    def move_thread_projectless(self, session: SessionRef) -> dict[str, object]:
        if self.local_adapter is None:
            return {"status": "failed", "session_id": session.session_id, "message": "No local database configured"}
        return self.local_adapter.move_codex_thread_projectless(session)

    def thread_sort_key(self, session: SessionRef) -> dict[str, object]:
        if self.local_adapter is None:
            return {"status": "failed", "session_id": session.session_id, "message": "No local database configured"}
        return self.local_adapter.codex_thread_sort_key(session)

    def thread_sort_keys(self, sessions: list[SessionRef]) -> dict[str, object]:
        if self.local_adapter is None:
            return {"status": "failed", "message": "No local database configured", "sort_keys": []}
        return self.local_adapter.codex_thread_sort_keys(sessions)

    def _release_payload(self, status: str, release: updater.Release, message: str, *, can_update: bool) -> dict[str, object]:
        return {
            "status": status,
            "current_version": __version__,
            "latest_version": release.version,
            "release_url": release.url,
            "asset_name": release.asset_name or "",
            "can_update": can_update,
            "message": message,
        }


class InjectedHelperServer(HelperServer):
    bridge_socket: Any = None


def _can_bind_loopback_port(port: int) -> bool:
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


def _find_available_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        if sys.platform == "win32" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def devtools_json_ready(port: int) -> bool:
    if not cdp_port_ready(port):
        return False
    try:
        list_targets(port)
        return True
    except Exception:
        return False


def select_windows_loopback_port(requested_port: int) -> int:
    if sys.platform != "win32" or _can_bind_loopback_port(requested_port):
        return requested_port
    if devtools_json_ready(requested_port):
        return requested_port
    return _find_available_loopback_port()


def build_codex_arguments(debug_port: int) -> list[str]:
    return [
        f"--remote-debugging-port={debug_port}",
        f"--remote-allow-origins=http://127.0.0.1:{debug_port}",
    ]


def build_macos_open_command(app_dir: Path, debug_port: int) -> list[str]:
    return ["open", "-W", "-a", str(app_dir), "--args", *build_codex_arguments(debug_port)]


def build_codex_executable(app_dir: Path) -> Path:
    if app_dir.suffix == ".app":
        return app_dir / "Contents" / "MacOS" / "Codex"
    candidates = [app_dir / "Codex.exe", app_dir / "codex.exe"]
    return next((path for path in candidates if path.exists()), candidates[-1])


def build_codex_command(app_dir: Path, debug_port: int) -> list[str]:
    return [str(build_codex_executable(app_dir)), *build_codex_arguments(debug_port)]


def packaged_app_user_model_id(app_dir: Path) -> str | None:
    package_dir = app_dir.parent if app_dir.name.lower() == "app" else app_dir
    if not package_dir.name.startswith("OpenAI.Codex_") or "__" not in package_dir.name:
        return None
    identity_name = package_dir.name.split("_", 1)[0]
    publisher_id = package_dir.name.rsplit("__", 1)[1]
    if not publisher_id:
        return None
    return f"{identity_name}_{publisher_id}!App"


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_uint32),
        ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    def __init__(self, value: str):
        parsed = uuid.UUID(value)
        data4 = bytes([parsed.clock_seq_hi_variant, parsed.clock_seq_low]) + parsed.node.to_bytes(6, "big")
        super().__init__(parsed.time_low, parsed.time_mid, parsed.time_hi_version, (ctypes.c_ubyte * 8)(*data4))


CLSCTX_LOCAL_SERVER = 0x4


def _raise_for_hresult(hr: int, operation: str) -> None:
    if hr < 0:
        raise OSError(f"{operation} failed with HRESULT 0x{hr & 0xFFFFFFFF:08X}")


def activate_packaged_app(app_user_model_id: str, arguments: str) -> int:
    if sys.platform != "win32":
        raise RuntimeError("Packaged app activation is only supported on Windows")

    ole32 = ctypes.OleDLL("ole32")
    ole32.CoInitializeEx.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    ole32.CoInitializeEx.restype = ctypes.c_long
    ole32.CoUninitialize.argtypes = []
    ole32.CoUninitialize.restype = None
    ole32.CoCreateInstance.argtypes = [
        ctypes.POINTER(_GUID),
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.POINTER(_GUID),
        ctypes.POINTER(ctypes.c_void_p),
    ]
    ole32.CoCreateInstance.restype = ctypes.c_long

    coinit_hr = ole32.CoInitializeEx(None, 2)
    should_uninitialize = coinit_hr >= 0
    if coinit_hr < 0 and coinit_hr != -2147417850:  # RPC_E_CHANGED_MODE
        _raise_for_hresult(coinit_hr, "CoInitializeEx")

    activation_manager = ctypes.c_void_p()
    try:
        clsid = _GUID("45BA127D-10A8-46EA-8AB7-56EA9078943C")
        iid = _GUID("2e941141-7f97-4756-ba1d-9decde894a3d")
        _raise_for_hresult(
            ole32.CoCreateInstance(ctypes.byref(clsid), None, CLSCTX_LOCAL_SERVER, ctypes.byref(iid), ctypes.byref(activation_manager)),
            "CoCreateInstance(ApplicationActivationManager)",
        )

        activate_application_type = ctypes.WINFUNCTYPE(
            ctypes.c_long,
            ctypes.c_void_p,
            ctypes.c_wchar_p,
            ctypes.c_wchar_p,
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong),
        )

        vtable = ctypes.cast(activation_manager, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        activate_application = activate_application_type(vtable[3])

        process_id = ctypes.c_ulong()
        _raise_for_hresult(
            activate_application(activation_manager, app_user_model_id, arguments, 0, ctypes.byref(process_id)),
            "ActivateApplication",
        )
        return int(process_id.value)
    finally:
        if activation_manager.value:
            release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(
                ctypes.cast(activation_manager, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents[2]
            )
            release(activation_manager)
        if should_uninitialize:
            ole32.CoUninitialize()


def launch_codex_app(app_dir: Path, debug_port: int) -> Any:
    if app_dir.suffix == ".app":
        prepare_macos_codex_relaunch(debug_port)
        return subprocess.Popen(build_macos_open_command(app_dir, debug_port), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    command = build_codex_command(app_dir, debug_port)
    app_user_model_id = packaged_app_user_model_id(app_dir) if sys.platform == "win32" else None
    if app_user_model_id:
        try:
            return subprocess.Popen(command)
        except OSError:
            return activate_packaged_app(app_user_model_id, subprocess.list2cmdline(build_codex_arguments(debug_port)))
    return subprocess.Popen(command)


def cdp_port_ready(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def _run_hidden_powershell(script: str, timeout: float = 6.0) -> str:
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return result.stdout or ""
    except (OSError, subprocess.SubprocessError):
        return ""


def find_windows_codex_processes() -> list[int]:
    output = _run_hidden_powershell(
        "Get-CimInstance Win32_Process -Filter \"Name='Codex.exe' OR Name='codex.exe'\" | "
        "Select-Object -ExpandProperty ProcessId"
    )
    return [int(line) for line in output.splitlines() if line.strip().isdigit()]


def stop_windows_codex_processes(pids: list[int]) -> None:
    if not pids:
        return
    script = "; ".join(f"Stop-Process -Id {pid} -Force -ErrorAction SilentlyContinue" for pid in pids)
    _run_hidden_powershell(script)


def wait_until_windows_codex_stops(timeout: float = 8.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        pids = find_windows_codex_processes()
        if not pids:
            return True
        stop_windows_codex_processes(pids)
        time.sleep(0.25)
    return not find_windows_codex_processes()


def prepare_windows_codex_relaunch(debug_port: int, *, force_restart: bool = False) -> None:
    if sys.platform != "win32":
        return
    if not force_restart and devtools_json_ready(debug_port):
        return
    pids = find_windows_codex_processes()
    if not pids:
        return
    stop_windows_codex_processes(pids)
    if not wait_until_windows_codex_stops():
        raise RuntimeError(
            "Codex is already running without the required DevTools port and could not be stopped. "
            "Quit Codex manually, then run Codex Mate again."
        )


def find_macos_codex_processes() -> list[int]:
    try:
        result = subprocess.run(
            ["ps", "ax", "-o", "pid=,command="],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=4,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if not hasattr(result, "returncode"):
        return []
    if result.returncode not in {0, 1}:
        return []
    return parse_macos_codex_process_lines(result.stdout or "")


def parse_macos_codex_process_lines(output: str) -> list[int]:
    pids: list[int] = []
    marker = "/Codex.app/Contents/MacOS/Codex"
    for line in output.splitlines():
        pid_text, _, command = line.strip().partition(" ")
        if not pid_text.isdigit():
            continue
        marker_index = command.find(marker)
        if marker_index < 0:
            continue
        after_marker = command[marker_index + len(marker) :]
        if after_marker and not after_marker[0].isspace():
            continue
        pids.append(int(pid_text))
    return pids


def stop_macos_codex_processes(pids: list[int]) -> None:
    if not pids:
        return
    subprocess.run(["kill", "-TERM", *[str(pid) for pid in pids]], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def wait_until_macos_codex_stops(timeout: float = 8.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        pids = find_macos_codex_processes()
        if not pids:
            return True
        time.sleep(0.25)
    pids = find_macos_codex_processes()
    if pids:
        subprocess.run(["kill", "-KILL", *[str(pid) for pid in pids]], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.25)
    return not find_macos_codex_processes()


def prepare_macos_codex_relaunch(debug_port: int, *, force_restart: bool = False) -> None:
    if sys.platform != "darwin":
        return
    if not force_restart and cdp_port_ready(debug_port):
        return
    pids = find_macos_codex_processes()
    if not pids:
        return
    stop_macos_codex_processes(pids)
    if not wait_until_macos_codex_stops():
        raise RuntimeError(
            "Codex is already running without the required DevTools port and could not be stopped. "
            "Quit Codex manually, then run Codex Mate again."
        )


def start_helper(service, host: str = "127.0.0.1", port: int = 57321) -> HelperServer:
    server = InjectedHelperServer(host, port, service)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def shutdown_helper(server: HelperServer) -> None:
    server.shutdown()
    server.server_close()


def native_feature_result_requires_restart(result: dict[str, object] | None) -> bool:
    return isinstance(result, dict) and result.get("status") == "updated"


def restart_running_codex_for_native_feature_change(debug_port: int) -> None:
    if sys.platform == "win32":
        prepare_windows_codex_relaunch(debug_port, force_restart=True)
        return
    if sys.platform == "darwin":
        prepare_macos_codex_relaunch(debug_port, force_restart=True)


def inject_with_retry(debug_port: int, script_path: Path, helper_port: int, service: ApiFirstDeleteService, attempts: int = 120, delay: float = 0.5) -> Any:
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            return inject_file(debug_port, script_path, helper_port, lambda path, payload: handle_bridge_request(service, path, payload))
        except Exception as exc:
            last_error = exc
            time.sleep(delay)
    if last_error is not None:
        raise RuntimeError(
            f"DevTools port {debug_port} did not become available. "
            "Quit any already-running Codex window and launch Codex Mate again."
        ) from last_error
    raise RuntimeError("Codex injection failed")


def launch_and_inject(app_dir: Path | None, db_path: Path | None, backup_dir: Path, debug_port: int, helper_port: int) -> tuple[HelperServer, Any]:
    resolved_app_dir = resolve_codex_app_dir(app_dir)
    if resolved_app_dir is None:
        raise RuntimeError("Codex App directory not found")
    debug_port = select_windows_loopback_port(debug_port)
    helper_port = select_windows_loopback_port(helper_port)
    prepare_windows_codex_relaunch(debug_port)
    native_feature_results: list[dict[str, object]] = []
    try:
        native_feature_results.append(native_features.ensure_bundled_plugin_marketplace_cache(app_dir=resolved_app_dir))
    except Exception as exc:
        try:
            from codex_mate import watcher

            watcher.log(f"bundled plugin cache sync skipped: {exc}")
        except Exception:
            pass
    try:
        native_feature_results.append(native_features.ensure_curated_plugin_marketplace_registered())
    except Exception as exc:
        try:
            from codex_mate import watcher

            watcher.log(f"curated plugin marketplace registration skipped: {exc}")
        except Exception:
            pass
    try:
        native_feature_results.append(native_features.ensure_role_specific_plugin_marketplace_registered())
    except Exception as exc:
        try:
            from codex_mate import watcher

            watcher.log(f"role-specific plugin marketplace registration skipped: {exc}")
        except Exception:
            pass
    if any(native_feature_result_requires_restart(result) for result in native_feature_results) and cdp_port_ready(debug_port):
        restart_running_codex_for_native_feature_change(debug_port)
    service = ApiFirstDeleteService(UnavailableApiAdapter(), db_path, backup_dir)
    server = start_helper(service, port=helper_port)
    codex_proc = None
    try:
        if not cdp_port_ready(debug_port):
            codex_proc = launch_codex_app(resolved_app_dir, debug_port)
        script_path = Path(__file__).parent / "inject" / "renderer-inject.js"
        server.bridge_socket = inject_with_retry(debug_port, script_path, server.port, service)
        return server, codex_proc
    except Exception as exc:
        shutdown_helper(server)
        if sys.platform == "win32":
            try:
                from codex_mate import watcher

                watcher.log(f"launcher injection failed; leaving Codex running: {exc}")
            except Exception:
                pass
        raise


def handle_bridge_request(service: ApiFirstDeleteService, path: str, payload: dict[str, object]) -> dict[str, object]:
    if path == "/delete":
        session = SessionRef(session_id=str(payload.get("session_id", "")), title=str(payload.get("title", "")))
        return service.delete(session).to_dict()
    if path == "/undo":
        return service.undo(str(payload.get("undo_token", ""))).to_dict()
    if path == "/archived-thread":
        session = service.find_archived_thread_by_title(str(payload.get("title", "")))
        return {"session_id": session.session_id, "title": session.title} if session else {"session_id": "", "title": ""}
    if path == "/check-update":
        return service.check_update()
    if path == "/update":
        return service.update()
    if path == "/export-markdown":
        session = SessionRef(session_id=str(payload.get("session_id", "")), title=str(payload.get("title", "")))
        return service.export_markdown(session)
    if path == "/conversation-timeline":
        session = SessionRef(session_id=str(payload.get("session_id", "")), title=str(payload.get("title", "")))
        return service.conversation_timeline(session)
    if path == "/move-thread-workspace":
        session = SessionRef(session_id=str(payload.get("session_id", "")), title=str(payload.get("title", "")))
        return service.move_thread_workspace(session, str(payload.get("target_cwd", "")))
    if path == "/move-thread-projectless":
        session = SessionRef(session_id=str(payload.get("session_id", "")), title=str(payload.get("title", "")))
        return service.move_thread_projectless(session)
    if path == "/thread-sort-key":
        session = SessionRef(session_id=str(payload.get("session_id", "")), title=str(payload.get("title", "")))
        return service.thread_sort_key(session)
    if path == "/thread-sort-keys":
        raw_sessions = payload.get("sessions", [])
        sessions = [
            SessionRef(session_id=str(item.get("session_id", "")), title=str(item.get("title", "")))
            for item in raw_sessions
            if isinstance(item, dict) and item.get("session_id")
        ] if isinstance(raw_sessions, list) else []
        return service.thread_sort_keys(sessions)
    if path == "/backend/status":
        return service.backend_status()
    if path == "/auth-enhancement-mode/status":
        return service.auth_enhancement_mode_status()
    if path == "/auth-enhancement-mode/set":
        return service.set_auth_enhancement_mode(str(payload.get("mode", "")))
    if path == "/provider-profile/status":
        return service.provider_profile_status()
    if path == "/provider-profile/apply":
        raw_profile = payload.get("profile", {})
        profile = raw_profile if isinstance(raw_profile, dict) else {}
        return service.apply_provider_profile(profile)
    if path == "/cc-switch/providers":
        return service.cc_switch_providers()
    if path == "/cc-switch/apply":
        return service.apply_cc_switch_provider(str(payload.get("source_id", "")))
    return {"status": DeleteStatus.FAILED.value, "session_id": str(payload.get("session_id", "")), "message": "Unknown bridge path"}
