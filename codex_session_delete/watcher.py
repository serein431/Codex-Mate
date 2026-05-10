from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path


WATCHER_INTERVAL_SECONDS = 3.0
TAKEOVER_GRACE_SECONDS = 0.8
CDP_PROBE_TIMEOUT_SECONDS = 0.5
CDP_WAIT_TIMEOUT_SECONDS = 25.0
KILL_WAIT_TIMEOUT_SECONDS = 8.0
SUPPORTED_PLATFORMS = {"win32", "darwin"}


def data_root() -> Path:
    return Path.home() / ".codex-session-delete"


def watcher_log_path() -> Path:
    return data_root() / "watcher.log"


def watcher_disabled_flag() -> Path:
    return data_root() / "watcher.disabled"


def log(line: str) -> None:
    path = watcher_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{datetime.now().isoformat(timespec='seconds')}] {line}\n")


def cdp_listening(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=CDP_PROBE_TIMEOUT_SECONDS):
            return True
    except OSError:
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


def find_windows_codex_processes() -> list[int]:
    script = (
        "Get-CimInstance Win32_Process -Filter \"Name='Codex.exe' OR Name='codex.exe'\" "
        "| Select-Object -ExpandProperty ProcessId"
    )
    output = _run_powershell(script)
    return _parse_pids(output)


def find_macos_codex_processes() -> list[int]:
    try:
        result = subprocess.run(
            ["pgrep", "-f", "/Contents/MacOS/Codex"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=4,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        log(f"pgrep failed: {exc}")
        return []
    if result.returncode not in {0, 1}:
        log(f"pgrep returned {result.returncode}: {result.stderr.strip() if result.stderr else ''}")
        return []
    return _parse_pids(result.stdout or "")


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
        if cdp_listening(port):
            return True
        time.sleep(0.5)
    return False


def wait_for_takeover_grace(port: int, observed_pids: list[int], grace_seconds: float = TAKEOVER_GRACE_SECONDS) -> bool:
    """Return True when takeover should proceed after a short startup grace period."""
    if grace_seconds <= 0:
        return True
    deadline = time.time() + grace_seconds
    observed = set(observed_pids)
    while True:
        if cdp_listening(port):
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


def spawn_launcher() -> subprocess.Popen | None:
    python = sys.executable
    pythonw = Path(python).with_name("pythonw.exe")
    exe = str(pythonw if sys.platform == "win32" and pythonw.exists() else python)
    args = [exe, "-m", "codex_session_delete", "launch"]
    popen_kwargs = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    if sys.platform == "win32":
        popen_kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP
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


def stop_launcher_processes() -> None:
    if sys.platform == "darwin":
        subprocess.run(
            ["pkill", "-f", "python.*-m codex_session_delete launch"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return
    script = (
        "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe' OR Name='python.exe'\" | "
        "Where-Object { $_.CommandLine -match 'codex_session_delete\\s+launch' } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
    )
    _run_powershell(script, timeout=6.0)


def takeover(debug_port: int) -> bool:
    """Perform one atomic takeover attempt: kill codex cleanly, spawn launcher, wait for CDP.

    Returns True on success (CDP up), False otherwise. On failure, caller should back off briefly.
    """
    # Step 1: Kill existing launcher processes (stale / failed) so we start from a known state.
    stop_launcher_processes()

    # Step 2: Kill all Codex.exe and wait for them to disappear.
    pids = find_codex_processes()
    log(f"takeover: killing {len(pids)} codex pid(s): {pids}")
    kill_processes(pids)
    if not wait_until_no_codex():
        log("takeover: codex processes did not exit in time, aborting this attempt")
        return False

    # Step 3: Give AppX activation machinery a moment to reset the "app is running" state.
    time.sleep(1.5)

    # Step 4: Spawn a fresh launcher that will activate the packaged app with CDP args.
    proc = spawn_launcher()
    if proc is None:
        return False

    # Step 5: Wait for CDP to come up. Launcher does injection in the background.
    if wait_for_cdp(debug_port):
        log(f"takeover: CDP is up on {debug_port} (launcher pid={proc.pid})")
        return True

    # Step 6: CDP did not come up. Clean up the launcher we spawned and any codex it started,
    # so the next pass can retry cleanly instead of staring at a broken window.
    log("takeover: CDP did not come up in time; cleaning up failed attempt")
    stop_launcher_processes()
    stragglers = find_codex_processes()
    if stragglers:
        kill_processes(stragglers)
        wait_until_no_codex(timeout=4.0)
    return False


def watch_loop(debug_port: int = 9229) -> int:
    if sys.platform not in SUPPORTED_PLATFORMS:
        log(f"watcher only supported on Windows and macOS (current={sys.platform})")
        return 1

    log(f"watcher started (interval={WATCHER_INTERVAL_SECONDS}s)")
    last_state = None
    backoff_until = 0.0

    while True:
        try:
            if watcher_disabled_flag().exists():
                if last_state != "disabled":
                    log("disabled flag present; idling")
                last_state = "disabled"
                time.sleep(WATCHER_INTERVAL_SECONDS)
                continue

            if cdp_listening(debug_port):
                if last_state != "cdp_ok":
                    log("CDP is up")
                last_state = "cdp_ok"
                time.sleep(WATCHER_INTERVAL_SECONDS)
                continue

            codex_pids = find_codex_processes()
            if not codex_pids:
                if last_state != "idle":
                    log("no Codex running; idling")
                last_state = "idle"
                time.sleep(WATCHER_INTERVAL_SECONDS)
                continue

            now = time.time()
            if now < backoff_until:
                if last_state != "backoff":
                    log(f"in backoff after failed takeover; {backoff_until - now:.1f}s remaining")
                last_state = "backoff"
                time.sleep(WATCHER_INTERVAL_SECONDS)
                continue

            log(f"Codex running without CDP (pids={codex_pids}); attempting takeover")
            last_state = "takeover"
            if not wait_for_takeover_grace(debug_port, codex_pids):
                time.sleep(WATCHER_INTERVAL_SECONDS)
                continue
            success = takeover(debug_port)
            if success:
                last_state = "cdp_ok"
            else:
                backoff_until = time.time() + 10.0
                last_state = "failed"
        except Exception as exc:
            log("watch loop error: " + "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
        except KeyboardInterrupt:
            log("watcher stopped")
            return 0

        time.sleep(WATCHER_INTERVAL_SECONDS)


def enable_watcher() -> None:
    flag = watcher_disabled_flag()
    if flag.exists():
        flag.unlink()


def disable_watcher() -> None:
    flag = watcher_disabled_flag()
    flag.parent.mkdir(parents=True, exist_ok=True)
    flag.touch()
