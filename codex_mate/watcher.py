from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from shutil import which

from codex_mate import history_sync, runtime
from codex_mate.cdp import list_targets


WATCHER_INTERVAL_SECONDS = 1.0
TAKEOVER_GRACE_SECONDS = 1.0
CDP_PROBE_TIMEOUT_SECONDS = 0.5
CDP_WAIT_TIMEOUT_SECONDS = 45.0
HELPER_WAIT_TIMEOUT_SECONDS = 8.0
KILL_WAIT_TIMEOUT_SECONDS = 8.0
TAKEOVER_FAILURE_BACKOFF_SECONDS = 30.0
TAKEOVER_SUCCESS_COOLDOWN_SECONDS = 15.0
DEFAULT_HELPER_PORT = 57321
SUPPORTED_PLATFORMS = {"win32", "darwin"}


def data_root() -> Path:
    return Path.home() / ".codex-mate"


def watcher_log_path() -> Path:
    return data_root() / "watcher.log"


def watcher_disabled_flag() -> Path:
    return data_root() / "watcher.disabled"


def watcher_lock_path(debug_port: int) -> Path:
    return data_root() / f"watcher-{debug_port}.lock"


def acquire_watcher_lock(debug_port: int):
    path = watcher_lock_path(debug_port)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = path.open("a+b")
        handle.seek(0)
        if sys.platform == "win32":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        handle.seek(0)
        handle.truncate()
        handle.write(str(os.getpid()).encode("ascii"))
        handle.flush()
        return handle
    except OSError:
        try:
            handle.close()  # type: ignore[name-defined]
        except Exception:
            pass
        return None


def release_watcher_lock(handle) -> None:
    try:
        if sys.platform == "win32":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass
    finally:
        handle.close()


def log(line: str) -> None:
    path = watcher_log_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"[{datetime.now().isoformat(timespec='seconds')}] {line}\n")
    except OSError:
        pass


def cdp_listening(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=CDP_PROBE_TIMEOUT_SECONDS):
            return True
    except OSError:
        return False


def helper_listening(port: int) -> bool:
    return cdp_listening(port)


def cdp_ready(port: int) -> bool:
    if not cdp_listening(port):
        return False
    try:
        list_targets(port)
        return True
    except Exception:
        return False


def _run_powershell(script: str, timeout: float = 8.0) -> str:
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return result.stdout or ""
    except (OSError, subprocess.SubprocessError) as exc:
        log(f"powershell failed: {exc}")
        return ""


def _parse_pids(output: str) -> list[int]:
    return [int(line) for line in output.splitlines() if line.strip().isdigit()]


def parse_windows_codex_process_details(output: str) -> list[tuple[int, Path]]:
    details: list[tuple[int, Path]] = []
    for line in output.splitlines():
        pid_text, separator, executable = line.strip().partition("\t")
        if not separator or not pid_text.isdigit() or not executable.strip():
            continue
        details.append((int(pid_text), Path(executable.strip())))
    return details


def find_windows_codex_process_details() -> list[tuple[int, Path]]:
    script = (
        "Get-CimInstance Win32_Process -Filter \"Name='Codex.exe' OR Name='codex.exe'\" "
        "| ForEach-Object { [string]$_.ProcessId + \"`t\" + [string]$_.ExecutablePath }"
    )
    return parse_windows_codex_process_details(_run_powershell(script))


def windows_codex_app_dir_from_details(details: list[tuple[int, Path]], pids: list[int] | None = None) -> Path | None:
    wanted = set(pids or [])
    for pid, executable in details:
        if wanted and pid not in wanted:
            continue
        if executable.name.lower() == "codex.exe":
            return executable.parent
    return None


def find_windows_codex_app_dir(pids: list[int] | None = None) -> Path | None:
    return windows_codex_app_dir_from_details(find_windows_codex_process_details(), pids)


def find_windows_codex_processes() -> list[int]:
    return [pid for pid, _executable in find_windows_codex_process_details()]


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
    except (OSError, subprocess.SubprocessError) as exc:
        log(f"ps failed: {exc}")
        return []
    if result.returncode not in {0, 1}:
        log(f"ps returned {result.returncode}: {result.stderr.strip() if result.stderr else ''}")
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


def find_codex_processes() -> list[int]:
    if sys.platform == "win32":
        return find_windows_codex_processes()
    if sys.platform == "darwin":
        return find_macos_codex_processes()
    return []


def kill_processes(pids: list[int], force: bool = False) -> None:
    if not pids:
        return
    if sys.platform == "darwin":
        signal = "-KILL" if force else "-TERM"
        subprocess.run(["kill", signal, *[str(pid) for pid in pids]], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    script = "; ".join(
        f"Stop-Process -Id {pid} -Force -ErrorAction SilentlyContinue" for pid in pids
    )
    _run_powershell(script, timeout=6.0)


def wait_until_no_codex(timeout: float = KILL_WAIT_TIMEOUT_SECONDS) -> bool:
    """Poll until no Codex process is left, or until timeout. Returns True if clean, False if still alive."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        remaining = find_codex_processes()
        if not remaining:
            return True
        # Be aggressive: re-issue kill for anything still alive.
        kill_processes(remaining)
        time.sleep(0.5)
    remaining = find_codex_processes()
    if remaining and sys.platform == "darwin":
        kill_processes(remaining, force=True)
        time.sleep(0.5)
    return not find_codex_processes()


def wait_for_cdp(port: int, timeout: float = CDP_WAIT_TIMEOUT_SECONDS) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if cdp_ready(port):
            return True
        time.sleep(0.5)
    return False


def wait_for_helper(port: int, timeout: float = HELPER_WAIT_TIMEOUT_SECONDS) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if helper_listening(port):
            return True
        time.sleep(0.5)
    return helper_listening(port)


def process_is_running(proc: subprocess.Popen | object | None) -> bool:
    if proc is None:
        return False
    poll = getattr(proc, "poll", None)
    if not callable(poll):
        return True
    try:
        return poll() is None
    except Exception:
        return False


def wait_for_takeover_grace(port: int, observed_pids: list[int], grace_seconds: float = TAKEOVER_GRACE_SECONDS) -> bool:
    """Return True when takeover should proceed after a short startup grace period."""
    if grace_seconds <= 0:
        return True
    deadline = time.time() + grace_seconds
    observed = set(observed_pids)
    while True:
        if cdp_ready(port):
            log("CDP appeared during takeover grace; skipping takeover")
            return False
        current = set(find_codex_processes())
        if not current:
            log("Codex exited during takeover grace; skipping takeover")
            return False
        if observed and current.isdisjoint(observed):
            log(f"Codex process set changed during takeover grace ({sorted(current)}); rechecking later")
            return False
        remaining = deadline - time.time()
        if remaining <= 0:
            return True
        time.sleep(min(0.25, remaining))


def spawn_launcher(app_dir: Path | None = None) -> subprocess.Popen | None:
    # The watcher already runs sync_history_before_takeover() before spawning the
    # launcher. Skipping the launch-time sync keeps takeover latency within the
    # CDP/helper wait budget and avoids killing the relaunch before injection.
    launch_args = ["launch", "--no-history-sync"]
    if app_dir is not None:
        launch_args.extend(["--app-dir", str(app_dir)])
    args = runtime.command_args(*launch_args, prefer_pythonw=True)
    popen_kwargs = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "env": runtime.independent_child_env(),
        "close_fds": True,
    }
    if sys.platform == "win32":
        popen_kwargs["creationflags"] = (
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
    elif sys.platform == "darwin":
        popen_kwargs["start_new_session"] = True
    try:
        return subprocess.Popen(args, **popen_kwargs)
    except Exception as exc:
        log(f"failed to spawn launcher: {exc}")
        return None


def launcher_command_available() -> bool:
    args = runtime.command_args("launch", prefer_pythonw=True)
    executable = args[0]
    resolved = which(executable) if not os.path.isabs(executable) else executable
    if not resolved or not Path(resolved).exists():
        log(f"launcher command unavailable: {executable}")
        return False
    return True


def sync_history_before_takeover() -> None:
    try:
        result = history_sync.sync_history_if_ready(history_sync.resolve_paths())
    except Exception as exc:
        log(f"history sync before takeover failed: {exc}")
        return
    if result.get("skipped"):
        return
    changed = int(result.get("updated_database_rows", 0)) + int(result.get("updated_session_files", 0))
    log(
        "history synced before takeover "
        f"(database rows={result.get('updated_database_rows')}, session files={result.get('updated_session_files')}, changed={changed})"
    )


def attach_to_running_codex(helper_port: int = DEFAULT_HELPER_PORT) -> bool:
    """Start the launcher/helper for a Codex process that already has CDP enabled."""
    stop_launcher_processes()
    app_dir = find_windows_codex_app_dir() if sys.platform == "win32" else None
    proc = spawn_launcher(app_dir)
    if proc is None:
        return False
    if wait_for_helper(helper_port) and process_is_running(proc):
        log(f"attach: helper is up on {helper_port} (launcher pid={getattr(proc, 'pid', 'unknown')})")
        return True
    log("attach: helper did not stay up; stopping launcher")
    stop_launcher_processes()
    return False


def stop_launcher_processes() -> None:
    modules = ("codex_mate", "_".join(("codex", "session", "delete")))
    if sys.platform == "darwin":
        for module in modules:
            subprocess.run(
                ["pkill", "-f", f"python.*-m {module} launch"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        subprocess.run(
            ["pkill", "-f", "CodexMate launch"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return
    module_pattern = "(" + "|".join(modules) + ")"
    script = (
        "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe' OR Name='python.exe' OR Name='CodexMate.exe'\" | "
        f"Where-Object {{ $_.CommandLine -match '{module_pattern}\\s+launch' -or $_.CommandLine -match 'CodexMate(\\.exe)?\"?\\s+launch' }} | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
    )
    _run_powershell(script, timeout=6.0)


def takeover(debug_port: int, app_dir: Path | None = None) -> bool:
    """Perform one atomic takeover attempt: kill codex cleanly, spawn launcher, wait for CDP.

    Returns True on success (CDP up), False otherwise. On failure, caller should back off briefly.
    """
    # Step 1: Kill existing launcher processes (stale / failed) so we start from a known state.
    stop_launcher_processes()

    # Step 2: Resolve the Codex executable while the original process is still alive.
    # Some Windows installs are not discoverable via Get-AppxPackage, so the
    # running process path is the most reliable launch target.
    pids = find_codex_processes()
    launch_app_dir = app_dir
    if sys.platform == "win32" and launch_app_dir is None:
        launch_app_dir = find_windows_codex_app_dir(pids)
        if launch_app_dir is None:
            log("takeover: Codex app directory could not be determined from the running process; skipping takeover")
            return False

    if not launcher_command_available():
        log("takeover: launcher command is unavailable; skipping takeover")
        return False

    # Step 3: Kill all Codex.exe and wait for them to disappear.
    log(f"takeover: killing {len(pids)} codex pid(s): {pids}")
    kill_processes(pids)
    if not wait_until_no_codex():
        log("takeover: codex processes did not exit in time, aborting this attempt")
        return False

    sync_history_before_takeover()

    # Step 4: Give AppX activation machinery a moment to reset the "app is running" state.
    time.sleep(1.5)

    # Step 5: Spawn a fresh launcher that will activate the packaged app with CDP args.
    proc = spawn_launcher(launch_app_dir)
    if proc is None:
        return False

    # Step 6: Wait for CDP and helper to come up. CDP alone is not enough:
    # without the helper server, injected buttons render but cannot perform work.
    if wait_for_cdp(debug_port) and wait_for_helper(DEFAULT_HELPER_PORT) and process_is_running(proc):
        log(f"takeover: CDP is up on {debug_port}, helper is up on {DEFAULT_HELPER_PORT} (launcher pid={proc.pid})")
        return True

    # Step 7: CDP/helper did not come up. Stop only the helper launcher and
    # leave Codex itself alone so the user can keep using the original app.
    log("takeover: CDP/helper did not come up in time; stopping launcher and leaving Codex running")
    stop_launcher_processes()
    return False


def watch_loop(debug_port: int = 9229, helper_port: int = DEFAULT_HELPER_PORT) -> int:
    if sys.platform not in SUPPORTED_PLATFORMS:
        log(f"watcher only supported on Windows and macOS (current={sys.platform})")
        return 1

    lock_handle = acquire_watcher_lock(debug_port)
    if lock_handle is None:
        log(f"another watcher is already running for debug port {debug_port}; exiting")
        return 0

    log(f"watcher started (interval={WATCHER_INTERVAL_SECONDS}s)")
    last_state = None
    backoff_until = 0.0
    cooldown_until = 0.0
    candidate_pids: tuple[int, ...] | None = None
    candidate_since = 0.0

    try:
        while True:
            try:
                if watcher_disabled_flag().exists():
                    if last_state != "disabled":
                        log("disabled flag present; idling")
                    last_state = "disabled"
                    time.sleep(WATCHER_INTERVAL_SECONDS)
                    continue

                if cdp_ready(debug_port):
                    if helper_listening(helper_port):
                        if last_state != "cdp_helper_ok":
                            log("CDP and helper are up")
                        last_state = "cdp_helper_ok"
                        candidate_pids = None
                        time.sleep(WATCHER_INTERVAL_SECONDS)
                        continue
                    now = time.time()
                    if now < backoff_until:
                        if last_state != "helper_backoff":
                            log(f"helper missing while CDP is up; in backoff {backoff_until - now:.1f}s remaining")
                        last_state = "helper_backoff"
                        time.sleep(WATCHER_INTERVAL_SECONDS)
                        continue
                    log("CDP is up but helper is missing; attaching helper without restarting Codex")
                    last_state = "attach_helper"
                    candidate_pids = None
                    if attach_to_running_codex(helper_port):
                        cooldown_until = time.time() + TAKEOVER_SUCCESS_COOLDOWN_SECONDS
                        last_state = "cdp_helper_ok"
                    else:
                        backoff_until = time.time() + TAKEOVER_FAILURE_BACKOFF_SECONDS
                        last_state = "failed"
                    time.sleep(WATCHER_INTERVAL_SECONDS)
                    continue

                codex_pids = find_codex_processes()
                if not codex_pids:
                    if last_state != "idle":
                        log("no Codex running; idling")
                    last_state = "idle"
                    candidate_pids = None
                    time.sleep(WATCHER_INTERVAL_SECONDS)
                    continue

                now = time.time()
                if now < cooldown_until:
                    if last_state != "cooldown":
                        log(f"in cooldown after takeover; {cooldown_until - now:.1f}s remaining")
                    last_state = "cooldown"
                    time.sleep(WATCHER_INTERVAL_SECONDS)
                    continue

                if now < backoff_until:
                    if last_state != "backoff":
                        log(f"in backoff after failed takeover; {backoff_until - now:.1f}s remaining")
                    last_state = "backoff"
                    time.sleep(WATCHER_INTERVAL_SECONDS)
                    continue

                codex_key = tuple(sorted(codex_pids))
                if candidate_pids != codex_key:
                    candidate_pids = codex_key
                    candidate_since = now
                    log(f"Codex running without CDP (pids={codex_pids}); waiting before takeover")
                    last_state = "grace"
                    time.sleep(WATCHER_INTERVAL_SECONDS)
                    continue

                if now - candidate_since < TAKEOVER_GRACE_SECONDS:
                    if last_state != "grace":
                        log(f"waiting for Codex CDP grace period (pids={codex_pids})")
                    last_state = "grace"
                    time.sleep(WATCHER_INTERVAL_SECONDS)
                    continue

                log(f"Codex running without CDP after grace period (pids={codex_pids}); attempting takeover")
                last_state = "takeover"
                if not wait_for_takeover_grace(debug_port, codex_pids, grace_seconds=0):
                    candidate_pids = None
                    time.sleep(WATCHER_INTERVAL_SECONDS)
                    continue
                success = takeover(debug_port)
                candidate_pids = None
                if success:
                    cooldown_until = time.time() + TAKEOVER_SUCCESS_COOLDOWN_SECONDS
                    last_state = "cdp_ok"
                else:
                    backoff_until = time.time() + TAKEOVER_FAILURE_BACKOFF_SECONDS
                    last_state = "failed"
            except Exception as exc:
                log("watch loop error: " + "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
            except KeyboardInterrupt:
                log("watcher stopped")
                return 0

            time.sleep(WATCHER_INTERVAL_SECONDS)
    finally:
        release_watcher_lock(lock_handle)


def enable_watcher() -> None:
    flag = watcher_disabled_flag()
    if flag.exists():
        flag.unlink()


def disable_watcher() -> None:
    flag = watcher_disabled_flag()
    flag.parent.mkdir(parents=True, exist_ok=True)
    flag.touch()
