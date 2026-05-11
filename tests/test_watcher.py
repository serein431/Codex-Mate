from __future__ import annotations

import socket
import sys
import types
from pathlib import Path

import pytest

from codex_mate import watcher


def test_cdp_listening_returns_true_when_bound():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]
        assert watcher.cdp_listening(port) is True


def test_cdp_listening_returns_false_when_closed():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    # After the probe socket closes, nothing should be listening on that port
    # (the port may get reused but the probe finishes with connection refused in normal conditions)
    assert watcher.cdp_listening(port) is False


def test_enable_watcher_removes_flag(tmp_path, monkeypatch):
    monkeypatch.setattr(watcher, "data_root", lambda: tmp_path)
    flag = tmp_path / "watcher.disabled"
    flag.parent.mkdir(parents=True, exist_ok=True)
    flag.touch()
    assert flag.exists()
    watcher.enable_watcher()
    assert not flag.exists()


def test_disable_watcher_creates_flag(tmp_path, monkeypatch):
    monkeypatch.setattr(watcher, "data_root", lambda: tmp_path)
    flag = tmp_path / "watcher.disabled"
    assert not flag.exists()
    watcher.disable_watcher()
    assert flag.exists()


def test_enable_watcher_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(watcher, "data_root", lambda: tmp_path)
    # Should not raise when flag does not exist
    watcher.enable_watcher()
    assert not (tmp_path / "watcher.disabled").exists()


def test_watch_loop_exits_on_non_windows(monkeypatch, tmp_path):
    monkeypatch.setattr(watcher, "data_root", lambda: tmp_path)
    monkeypatch.setattr(watcher.sys, "platform", "linux")
    assert watcher.watch_loop() == 1


def test_watch_loop_exits_when_another_watcher_holds_lock(monkeypatch, tmp_path):
    logs = []
    monkeypatch.setattr(watcher, "data_root", lambda: tmp_path)
    monkeypatch.setattr(watcher.sys, "platform", "win32")
    monkeypatch.setattr(watcher, "acquire_watcher_lock", lambda debug_port: None)
    monkeypatch.setattr(watcher, "log", lambda line: logs.append(line))

    assert watcher.watch_loop(debug_port=9229) == 0
    assert "another watcher is already running" in logs[0]


def test_find_codex_processes_uses_windows_backend(monkeypatch):
    monkeypatch.setattr(watcher.sys, "platform", "win32")
    monkeypatch.setattr(watcher, "find_windows_codex_processes", lambda: [101, 202])

    assert watcher.find_codex_processes() == [101, 202]


def test_find_codex_processes_uses_macos_backend(monkeypatch):
    monkeypatch.setattr(watcher.sys, "platform", "darwin")
    monkeypatch.setattr(watcher, "find_macos_codex_processes", lambda: [303])

    assert watcher.find_codex_processes() == [303]


def test_find_macos_codex_processes_parses_ps_output(monkeypatch):
    class Result:
        returncode = 0
        stdout = (
            "111 /Applications/Codex.app/Contents/MacOS/Codex\n"
            "222 /Applications/Codex Manager.app/Contents/MacOS/Codex Manager\n"
            "333 /Users/me/Downloads/Codex.app/Contents/MacOS/Codex --remote-debugging-port=9229\n"
        )

    calls = []
    monkeypatch.setattr(watcher.subprocess, "run", lambda command, **kwargs: calls.append((command, kwargs)) or Result())

    assert watcher.find_macos_codex_processes() == [111, 333]
    assert calls[0][0] == ["ps", "ax", "-o", "pid=,command="]


def test_watch_loop_runs_on_macos_until_keyboard_interrupt(monkeypatch, tmp_path):
    monkeypatch.setattr(watcher, "data_root", lambda: tmp_path)
    monkeypatch.setattr(watcher.sys, "platform", "darwin")
    monkeypatch.setattr(watcher, "acquire_watcher_lock", lambda debug_port: object())
    monkeypatch.setattr(watcher, "release_watcher_lock", lambda handle: None)
    monkeypatch.setattr(watcher, "cdp_listening", lambda port: False)
    monkeypatch.setattr(watcher, "find_codex_processes", lambda: [])

    def stop(_seconds):
        raise KeyboardInterrupt

    monkeypatch.setattr(watcher.time, "sleep", stop)

    assert watcher.watch_loop() == 0


def test_spawn_launcher_detaches_on_macos(monkeypatch):
    calls = []
    monkeypatch.setattr(watcher.sys, "platform", "darwin")
    monkeypatch.setattr(watcher.sys, "executable", "/usr/local/bin/python3")
    monkeypatch.setattr(watcher.subprocess, "Popen", lambda args, **kwargs: calls.append((args, kwargs)) or object())

    watcher.spawn_launcher()

    assert calls[0][0] == ["/usr/local/bin/python3", "-m", "codex_mate", "launch"]
    assert calls[0][1]["start_new_session"] is True


def test_spawn_launcher_windows_flags_are_cross_platform_safe(monkeypatch, tmp_path):
    calls = []
    fake_python = tmp_path / "python.exe"
    monkeypatch.setattr(watcher.sys, "platform", "win32")
    monkeypatch.setattr(watcher.sys, "executable", str(fake_python))
    monkeypatch.setattr(watcher.runtime, "independent_child_env", lambda: {"PYINSTALLER_RESET_ENVIRONMENT": "1"})
    monkeypatch.setattr(watcher.subprocess, "Popen", lambda args, **kwargs: calls.append((args, kwargs)) or object())

    watcher.spawn_launcher()

    assert calls[0][0] == [str(fake_python), "-m", "codex_mate", "launch"]
    assert "creationflags" in calls[0][1]
    assert calls[0][1]["env"]["PYINSTALLER_RESET_ENVIRONMENT"] == "1"


def test_stop_launcher_processes_cleans_legacy_macos_module(monkeypatch):
    calls = []
    monkeypatch.setattr(watcher.sys, "platform", "darwin")
    monkeypatch.setattr(watcher.subprocess, "run", lambda command, **kwargs: calls.append(command))

    watcher.stop_launcher_processes()

    assert ["pkill", "-f", "python.*-m codex_mate launch"] in calls
    assert ["pkill", "-f", f"python.*-m {'_'.join(('codex', 'session', 'delete'))} launch"] in calls
    assert ["pkill", "-f", "CodexMate launch"] in calls


def test_wait_until_no_codex_success(monkeypatch):
    calls = {"n": 0}

    def find() -> list[int]:
        calls["n"] += 1
        # First poll: one process, subsequent polls: empty
        return [1234] if calls["n"] == 1 else []

    monkeypatch.setattr(watcher, "find_codex_processes", find)
    killed: list[list[int]] = []
    monkeypatch.setattr(watcher, "kill_processes", lambda pids: killed.append(list(pids)))
    assert watcher.wait_until_no_codex(timeout=2.0) is True


def test_wait_until_no_codex_times_out(monkeypatch):
    monkeypatch.setattr(watcher, "find_codex_processes", lambda: [1])
    monkeypatch.setattr(watcher, "kill_processes", lambda pids, force=False: None)
    assert watcher.wait_until_no_codex(timeout=0.5) is False


def test_wait_for_cdp_returns_true_when_listening(monkeypatch):
    seq = iter([False, False, True])
    monkeypatch.setattr(watcher, "cdp_ready", lambda port: next(seq))
    assert watcher.wait_for_cdp(port=9229, timeout=2.0) is True


def test_wait_for_cdp_returns_false_on_timeout(monkeypatch):
    monkeypatch.setattr(watcher, "cdp_ready", lambda port: False)
    assert watcher.wait_for_cdp(port=9229, timeout=0.3) is False


def test_wait_for_helper_returns_true_when_listening(monkeypatch):
    seq = iter([False, True])
    monkeypatch.setattr(watcher, "helper_listening", lambda port: next(seq))

    assert watcher.wait_for_helper(port=57321, timeout=2.0) is True


def test_attach_to_running_codex_starts_helper_without_killing_codex(monkeypatch):
    events = []

    class Proc:
        pid = 456

        def poll(self):
            return None

    monkeypatch.setattr(watcher, "stop_launcher_processes", lambda: events.append(("stop-launchers", [])))
    monkeypatch.setattr(watcher, "spawn_launcher", lambda: events.append(("spawn", [])) or Proc())
    monkeypatch.setattr(watcher, "wait_for_helper", lambda port: events.append(("wait-helper", [port])) or True)
    monkeypatch.setattr(watcher, "kill_processes", lambda pids, force=False: events.append(("kill", list(pids))))

    assert watcher.attach_to_running_codex(helper_port=57321) is True
    assert events == [("stop-launchers", []), ("spawn", []), ("wait-helper", [57321])]


def test_wait_for_takeover_grace_skips_when_cdp_appears(monkeypatch):
    cdp_states = iter([False, True])
    monkeypatch.setattr(watcher, "cdp_ready", lambda port: next(cdp_states))
    monkeypatch.setattr(watcher, "find_codex_processes", lambda: [123])
    monkeypatch.setattr(watcher.time, "sleep", lambda seconds: None)

    assert watcher.wait_for_takeover_grace(port=9229, observed_pids=[123], grace_seconds=2.0) is False


def test_watcher_log_is_best_effort(monkeypatch, tmp_path):
    log_path = tmp_path / "blocked" / "watcher.log"
    monkeypatch.setattr(watcher, "watcher_log_path", lambda: log_path)
    monkeypatch.setattr(type(log_path.parent), "mkdir", lambda *args, **kwargs: (_ for _ in ()).throw(PermissionError("blocked")))

    watcher.log("still keep running")


def test_wait_for_takeover_grace_allows_takeover_after_timeout(monkeypatch):
    times = iter([0.0, 0.0, 0.3])
    monkeypatch.setattr(watcher.time, "time", lambda: next(times))
    monkeypatch.setattr(watcher, "cdp_ready", lambda port: False)
    monkeypatch.setattr(watcher, "find_codex_processes", lambda: [123])
    monkeypatch.setattr(watcher.time, "sleep", lambda seconds: None)

    assert watcher.wait_for_takeover_grace(port=9229, observed_pids=[123], grace_seconds=0.2) is True


def test_kill_processes_uses_sigterm_then_sigkill_on_macos(monkeypatch):
    calls = []
    monkeypatch.setattr(watcher.sys, "platform", "darwin")
    monkeypatch.setattr(watcher.subprocess, "run", lambda command, **kwargs: calls.append(command))

    watcher.kill_processes([111, 222])
    watcher.kill_processes([111, 222], force=True)

    assert calls[0] == ["kill", "-TERM", "111", "222"]
    assert calls[1] == ["kill", "-KILL", "111", "222"]


def test_wait_until_no_codex_escalates_on_macos_timeout(monkeypatch):
    kills = []
    monkeypatch.setattr(watcher.sys, "platform", "darwin")
    monkeypatch.setattr(watcher, "find_codex_processes", lambda: [999])
    monkeypatch.setattr(watcher, "kill_processes", lambda pids, force=False: kills.append((list(pids), force)))
    monkeypatch.setattr(watcher.time, "sleep", lambda seconds: None)

    assert watcher.wait_until_no_codex(timeout=0.0) is False
    assert kills == [([999], True)]


def test_takeover_failure_leaves_codex_processes_running(monkeypatch):
    events = []
    monkeypatch.setattr(watcher, "stop_launcher_processes", lambda: events.append(("stop-launchers", [])))
    monkeypatch.setattr(watcher, "find_codex_processes", lambda: [123])
    monkeypatch.setattr(watcher, "kill_processes", lambda pids, force=False: events.append(("kill", list(pids))))
    monkeypatch.setattr(watcher, "wait_until_no_codex", lambda timeout=watcher.KILL_WAIT_TIMEOUT_SECONDS: True)

    class Proc:
        pid = 456

    monkeypatch.setattr(watcher, "spawn_launcher", lambda: Proc())
    monkeypatch.setattr(watcher, "wait_for_cdp", lambda port: False)
    monkeypatch.setattr(watcher.time, "sleep", lambda seconds: None)

    assert watcher.takeover(debug_port=9229) is False
    assert events == [("stop-launchers", []), ("kill", [123]), ("stop-launchers", [])]


def test_takeover_requires_helper_after_cdp(monkeypatch):
    events = []
    monkeypatch.setattr(watcher, "stop_launcher_processes", lambda: events.append(("stop-launchers", [])))
    monkeypatch.setattr(watcher, "find_codex_processes", lambda: [123])
    monkeypatch.setattr(watcher, "kill_processes", lambda pids, force=False: events.append(("kill", list(pids))))
    monkeypatch.setattr(watcher, "wait_until_no_codex", lambda timeout=watcher.KILL_WAIT_TIMEOUT_SECONDS: True)

    class Proc:
        pid = 456

        def poll(self):
            return None

    monkeypatch.setattr(watcher, "spawn_launcher", lambda: Proc())
    monkeypatch.setattr(watcher, "wait_for_cdp", lambda port: True)
    monkeypatch.setattr(watcher, "wait_for_helper", lambda port: False)
    monkeypatch.setattr(watcher.time, "sleep", lambda seconds: None)

    assert watcher.takeover(debug_port=9229) is False
    assert events == [("stop-launchers", []), ("kill", [123]), ("stop-launchers", [])]
