from pathlib import Path

import pytest

from codex_mate import cli, launcher
from codex_mate.launcher import build_codex_command, launch_codex_app, packaged_app_user_model_id


class FakeServer:
    port = 57321

    def __init__(self):
        self.shutdown_called = False
        self.server_close_called = False

    def shutdown(self):
        self.shutdown_called = True

    def server_close(self):
        self.server_close_called = True


class FakeProcess:
    def __init__(self):
        self.waited = False

    def wait(self):
        self.waited = True


def test_launch_codex_windows_adds_remote_debugging_port(monkeypatch):
    app_dir = Path("C:/Codex/app")
    popen_calls = []
    monkeypatch.setattr(launcher.subprocess, "Popen", lambda args, **kw: popen_calls.append(args))

    launch_codex_app(app_dir, 9229)

    assert popen_calls
    assert str(app_dir / "Codex.exe") in popen_calls[0][0] or str(app_dir / "codex.exe") in popen_calls[0][0]
    assert "--remote-debugging-port=9229" in popen_calls[0]


def test_launch_codex_windows_allows_devtools_websocket_origin(monkeypatch):
    app_dir = Path("C:/Codex/app")
    popen_calls = []
    monkeypatch.setattr(launcher.subprocess, "Popen", lambda args, **kw: popen_calls.append(args))

    launch_codex_app(app_dir, 9229)

    assert "--remote-allow-origins=http://127.0.0.1:9229" in popen_calls[0]


def test_launch_codex_macos_uses_open_command(monkeypatch, tmp_path):
    app = tmp_path / "Codex.app"
    (app / "Contents" / "MacOS").mkdir(parents=True)
    run_calls = []
    monkeypatch.setattr(launcher.subprocess, "run", lambda args, **kw: run_calls.append(args))

    proc = launch_codex_app(app, 9229)

    assert proc is None
    open_calls = [call for call in run_calls if call and call[0] == "open"]
    assert len(open_calls) == 1
    assert open_calls[0] == [
        "open",
        str(app),
        "--args",
        "--remote-debugging-port=9229",
        "--remote-allow-origins=http://127.0.0.1:9229",
    ]


def test_launcher_macos_process_scan_ignores_codex_manager(monkeypatch):
    class Result:
        returncode = 0
        stdout = (
            "111 /Applications/Codex.app/Contents/MacOS/Codex\n"
            "222 /Applications/Codex Manager.app/Contents/MacOS/Codex Manager\n"
            "333 /tmp/Codex.app/Contents/MacOS/Codex --remote-debugging-port=9229\n"
        )

    monkeypatch.setattr(launcher.subprocess, "run", lambda *args, **kwargs: Result())

    assert launcher.find_macos_codex_processes() == [111, 333]


def test_macos_prelaunch_cleanup_stops_running_codex_when_cdp_is_absent(monkeypatch):
    events = []
    monkeypatch.setattr(launcher.sys, "platform", "darwin")
    monkeypatch.setattr(launcher, "cdp_port_ready", lambda port: False)
    monkeypatch.setattr(launcher, "find_macos_codex_processes", lambda: [111, 222])
    monkeypatch.setattr(launcher, "stop_macos_codex_processes", lambda pids: events.append(("stop", pids)))
    monkeypatch.setattr(launcher, "wait_until_macos_codex_stops", lambda: events.append(("wait", [])) or True)

    launcher.prepare_macos_codex_relaunch(debug_port=9229)

    assert events == [("stop", [111, 222]), ("wait", [])]


def test_macos_prelaunch_cleanup_skips_when_cdp_is_ready(monkeypatch):
    events = []
    monkeypatch.setattr(launcher.sys, "platform", "darwin")
    monkeypatch.setattr(launcher, "cdp_port_ready", lambda port: True)
    monkeypatch.setattr(launcher, "find_macos_codex_processes", lambda: (_ for _ in ()).throw(AssertionError("should not scan")))
    monkeypatch.setattr(launcher, "stop_macos_codex_processes", lambda pids: events.append(("stop", pids)))

    launcher.prepare_macos_codex_relaunch(debug_port=9229)

    assert events == []


def test_launch_codex_macos_prepares_relaunch_before_open(monkeypatch, tmp_path):
    app = tmp_path / "Codex.app"
    (app / "Contents" / "MacOS").mkdir(parents=True)
    events = []
    monkeypatch.setattr(launcher.sys, "platform", "darwin")
    monkeypatch.setattr(launcher, "prepare_macos_codex_relaunch", lambda debug_port: events.append(("prepare", debug_port)))
    monkeypatch.setattr(launcher.subprocess, "run", lambda args, **kw: events.append(("open", args)))

    launch_codex_app(app, 9229)

    assert events[0] == ("prepare", 9229)
    assert events[1][0] == "open"


def test_packaged_app_user_model_id_from_windowsapps_path():
    app_dir = Path("C:/Program Files/WindowsApps/OpenAI.Codex_26.506.2212.0_x64__2p2nqsd0c76g0/app")

    assert packaged_app_user_model_id(app_dir) == "OpenAI.Codex_2p2nqsd0c76g0!App"


def test_packaged_app_user_model_id_ignores_non_packaged_path():
    app_dir = Path("C:/Codex/app")

    assert packaged_app_user_model_id(app_dir) is None


def test_launch_uses_packaged_activation_for_windowsapps(monkeypatch):
    app_dir = Path("C:/Program Files/WindowsApps/OpenAI.Codex_26.506.2212.0_x64__2p2nqsd0c76g0/app")
    activated = []
    launched = []
    monkeypatch.setattr(launcher.sys, "platform", "win32")
    monkeypatch.setattr(
        launcher,
        "activate_packaged_app",
        lambda aumid, arguments: activated.append((aumid, arguments)) or 1234,
    )
    monkeypatch.setattr(launcher.subprocess, "Popen", lambda command: launched.append(command))

    assert launcher.launch_codex_app(app_dir, 9229) == 1234

    assert activated == [(
        "OpenAI.Codex_2p2nqsd0c76g0!App",
        "--remote-debugging-port=9229 --remote-allow-origins=http://127.0.0.1:9229",
    )]
    assert launched == []


def test_windows_port_selector_uses_ephemeral_port_when_default_is_busy(monkeypatch):
    monkeypatch.setattr(launcher.sys, "platform", "win32")
    monkeypatch.setattr(launcher, "_can_bind_loopback_port", lambda port: port != 9229)
    monkeypatch.setattr(launcher, "devtools_json_ready", lambda port: False)
    monkeypatch.setattr(launcher, "_find_available_loopback_port", lambda: 43001)

    assert launcher.select_windows_loopback_port(9229) == 43001


def test_windows_port_selector_keeps_busy_port_when_devtools_is_ready(monkeypatch):
    monkeypatch.setattr(launcher.sys, "platform", "win32")
    monkeypatch.setattr(launcher, "_can_bind_loopback_port", lambda port: False)
    monkeypatch.setattr(launcher, "devtools_json_ready", lambda port: port == 9229)
    monkeypatch.setattr(launcher, "_find_available_loopback_port", lambda: (_ for _ in ()).throw(AssertionError("should not allocate")))

    assert launcher.select_windows_loopback_port(9229) == 9229


def test_non_windows_port_selector_keeps_requested_port(monkeypatch):
    monkeypatch.setattr(launcher.sys, "platform", "darwin")
    monkeypatch.setattr(launcher, "_can_bind_loopback_port", lambda port: False)

    assert launcher.select_windows_loopback_port(9229) == 9229


def test_windows_prelaunch_cleanup_stops_running_codex_when_cdp_is_absent(monkeypatch):
    events = []
    monkeypatch.setattr(launcher.sys, "platform", "win32")
    monkeypatch.setattr(launcher, "devtools_json_ready", lambda port: False)
    monkeypatch.setattr(launcher, "find_windows_codex_processes", lambda: [111, 222])
    monkeypatch.setattr(launcher, "stop_windows_codex_processes", lambda pids: events.append(("stop", pids)))
    monkeypatch.setattr(launcher, "wait_until_windows_codex_stops", lambda: events.append(("wait", [])) or True)

    launcher.prepare_windows_codex_relaunch(debug_port=9229)

    assert events == [("stop", [111, 222]), ("wait", [])]


def test_windows_prelaunch_cleanup_skips_when_cdp_is_ready(monkeypatch):
    events = []
    monkeypatch.setattr(launcher.sys, "platform", "win32")
    monkeypatch.setattr(launcher, "devtools_json_ready", lambda port: True)
    monkeypatch.setattr(launcher, "find_windows_codex_processes", lambda: (_ for _ in ()).throw(AssertionError("should not scan")))
    monkeypatch.setattr(launcher, "stop_windows_codex_processes", lambda pids: events.append(("stop", pids)))

    launcher.prepare_windows_codex_relaunch(debug_port=9229)

    assert events == []


def test_cli_keeps_helper_server_alive_after_injection(monkeypatch):
    waited = []
    monkeypatch.setattr(cli, "launch_and_inject", lambda *args: (FakeServer(), None))
    monkeypatch.setattr(cli, "wait_for_shutdown", lambda server, proc: waited.append(server.port))

    exit_code = cli.main([])

    assert exit_code == 0
    assert waited == [57321]


def test_cli_launch_subcommand_keeps_helper_server_alive_after_injection(monkeypatch):
    waited = []
    calls = []
    monkeypatch.setattr(cli, "launch_and_inject", lambda *args: calls.append(args) or (FakeServer(), None))
    monkeypatch.setattr(cli, "wait_for_shutdown", lambda server, proc: waited.append(server.port))

    exit_code = cli.main(["launch"])

    assert exit_code == 0
    assert waited == [57321]
    assert len(calls) == 1


def test_cli_install_dispatches_to_platform_installer(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(cli, "install_codex_mate", lambda options: calls.append(options))

    exit_code = cli.main(["install", "--install-root", str(tmp_path), "--launcher-command", "python -m codex_mate"])

    assert exit_code == 0
    assert len(calls) == 1
    assert calls[0].install_root == tmp_path
    assert calls[0].launcher_command == "python -m codex_mate"


def test_cli_uninstall_dispatches_to_platform_installer(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(cli, "uninstall_codex_mate", lambda options: calls.append(options))

    exit_code = cli.main(["uninstall", "--install-root", str(tmp_path), "--remove-data"])

    assert exit_code == 0
    assert len(calls) == 1
    assert calls[0].install_root == tmp_path
    assert calls[0].remove_data is True


def test_launch_retries_injection_until_codex_page_is_ready(monkeypatch, tmp_path):
    attempts = []
    monkeypatch.setattr(launcher, "resolve_codex_app_dir", lambda app_dir=None: tmp_path)
    monkeypatch.setattr(launcher, "prepare_windows_codex_relaunch", lambda debug_port: None)
    monkeypatch.setattr(launcher, "start_helper", lambda *args, **kwargs: FakeServer())
    monkeypatch.setattr(launcher, "launch_codex_app", lambda *args: None)

    def inject_after_retry(*args):
        attempts.append(args)
        if len(attempts) == 1:
            raise RuntimeError("CDP page not ready")
        return {"result": {}}

    monkeypatch.setattr(launcher, "inject_file", inject_after_retry)
    monkeypatch.setattr(launcher.time, "sleep", lambda seconds: None)

    server, proc = launcher.launch_and_inject(None, None, tmp_path / "backups", 9229, 57321)

    assert server.port == 57321
    assert len(attempts) == 2


def test_inject_with_retry_reports_friendly_cdp_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(launcher, "inject_file", lambda *args, **kwargs: (_ for _ in ()).throw(ConnectionError("refused")))
    monkeypatch.setattr(launcher.time, "sleep", lambda seconds: None)

    with pytest.raises(RuntimeError, match="DevTools port 9229 did not become available"):
        launcher.inject_with_retry(9229, tmp_path / "inject.js", 57321, object(), attempts=2, delay=0)


def test_launch_and_inject_returns_windows_packaged_process_id(monkeypatch, tmp_path):
    monkeypatch.setattr(launcher, "resolve_codex_app_dir", lambda app_dir=None: tmp_path)
    monkeypatch.setattr(launcher, "prepare_windows_codex_relaunch", lambda debug_port: None)
    monkeypatch.setattr(launcher, "start_helper", lambda *args, **kwargs: FakeServer())
    monkeypatch.setattr(launcher, "launch_codex_app", lambda *args: 1234)
    monkeypatch.setattr(launcher, "inject_with_retry", lambda *args, **kwargs: {"result": {}})

    server, proc = launcher.launch_and_inject(None, None, tmp_path / "backups", 9229, 57321)

    assert server.port == 57321
    assert proc == 1234


def test_launch_and_inject_closes_helper_when_injection_fails(monkeypatch, tmp_path):
    server = FakeServer()
    monkeypatch.setattr(launcher, "resolve_codex_app_dir", lambda app_dir=None: tmp_path)
    monkeypatch.setattr(launcher, "prepare_windows_codex_relaunch", lambda debug_port: None)
    monkeypatch.setattr(launcher, "start_helper", lambda *args, **kwargs: server)
    monkeypatch.setattr(launcher, "launch_codex_app", lambda *args: 1234)
    monkeypatch.setattr(launcher, "inject_with_retry", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("inject failed")))

    with pytest.raises(RuntimeError, match="inject failed"):
        launcher.launch_and_inject(None, None, tmp_path / "backups", 9229, 57321)

    assert server.shutdown_called is True
    assert server.server_close_called is True


def test_launch_and_inject_leaves_codex_running_when_injection_fails(monkeypatch, tmp_path):
    from codex_mate import watcher

    logs = []
    run_calls = []
    monkeypatch.setattr(launcher.sys, "platform", "win32")
    monkeypatch.setattr(launcher, "resolve_codex_app_dir", lambda app_dir=None: tmp_path)
    monkeypatch.setattr(launcher, "prepare_windows_codex_relaunch", lambda debug_port: None)
    monkeypatch.setattr(launcher, "start_helper", lambda *args, **kwargs: FakeServer())
    monkeypatch.setattr(launcher, "launch_codex_app", lambda *args: 1234)
    monkeypatch.setattr(launcher, "inject_with_retry", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("inject failed")))
    monkeypatch.setattr(launcher.subprocess, "run", lambda *args, **kwargs: run_calls.append((args, kwargs)))
    monkeypatch.setattr(watcher, "log", lambda line: logs.append(line))

    with pytest.raises(RuntimeError, match="inject failed"):
        launcher.launch_and_inject(None, None, tmp_path / "backups", 9229, 57321)

    assert run_calls == []
    assert logs == ["launcher injection failed; leaving Codex running: inject failed"]


def test_launch_uses_resolved_app_dir(monkeypatch, tmp_path):
    launched = []
    mac_app = tmp_path / "Applications" / "OpenAI Codex.app"
    executable = mac_app / "Contents" / "MacOS" / "Codex"
    executable.parent.mkdir(parents=True)
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr(launcher, "resolve_codex_app_dir", lambda app_dir=None: mac_app)
    monkeypatch.setattr(launcher, "prepare_windows_codex_relaunch", lambda debug_port: None)
    monkeypatch.setattr(launcher, "start_helper", lambda *args, **kwargs: FakeServer())
    monkeypatch.setattr(launcher.subprocess, "run", lambda args, **kw: launched.append(args))
    monkeypatch.setattr(launcher, "inject_with_retry", lambda *args, **kwargs: {"result": {}})

    launcher.launch_and_inject(None, None, tmp_path / "backups", 9229, 57321)

    open_calls = [call for call in launched if call and call[0] == "open"]
    assert len(open_calls) == 1
    assert str(executable) not in open_calls[0]


def test_cli_stops_existing_windows_launchers_before_launch(monkeypatch):
    commands = []
    monkeypatch.setattr(cli.sys, "platform", "win32")
    monkeypatch.setattr(cli.os, "getpid", lambda: 9876)
    monkeypatch.setattr(cli.subprocess, "run", lambda command, **kwargs: commands.append((command, kwargs)))

    cli.stop_existing_windows_launchers()

    assert len(commands) == 1
    command, kwargs = commands[0]
    assert command[:3] == ["powershell", "-NoProfile", "-Command"]
    assert "codex_mate" in command[3]
    assert "_".join(("codex", "session", "delete")) in command[3]
    assert "CodexMate" in command[3]
    assert "pythonw?" in command[3]
    assert "Stop-Process" in command[3]
    assert kwargs["env"]["CODEX_MATE_PID"] == "9876"
    assert kwargs["check"] is False


def test_cli_skips_launcher_cleanup_on_non_windows(monkeypatch):
    commands = []
    monkeypatch.setattr(cli.sys, "platform", "linux")
    monkeypatch.setattr(cli.subprocess, "run", lambda command, **kwargs: commands.append((command, kwargs)))

    cli.stop_existing_windows_launchers()

    assert commands == []


def test_cli_launch_runs_launcher_cleanup_before_injection(monkeypatch):
    events = []
    monkeypatch.setattr(cli, "stop_existing_windows_launchers", lambda: events.append("cleanup"))
    monkeypatch.setattr(cli, "sync_history_before_launch", lambda args: events.append("history-sync"))
    monkeypatch.setattr(cli, "launch_and_inject", lambda *args: events.append("launch") or (FakeServer(), None))
    monkeypatch.setattr(cli, "wait_for_shutdown", lambda server, proc: events.append("wait"))

    exit_code = cli.main(["launch"])

    assert exit_code == 0
    assert events == ["cleanup", "history-sync", "launch", "wait"]


def test_cli_launch_can_skip_history_sync(monkeypatch):
    events = []
    monkeypatch.setattr(cli, "stop_existing_windows_launchers", lambda: events.append("cleanup"))
    monkeypatch.setattr(cli, "sync_history_before_launch", lambda args: events.append("history-sync"))
    monkeypatch.setattr(cli, "launch_and_inject", lambda *args: events.append("launch") or (FakeServer(), None))
    monkeypatch.setattr(cli, "wait_for_shutdown", lambda server, proc: events.append("wait"))

    exit_code = cli.main(["launch", "--no-history-sync"])

    assert exit_code == 0
    assert events == ["cleanup", "launch", "wait"]


def test_cli_launch_checks_update_before_injection(monkeypatch):
    events = []
    monkeypatch.setattr(cli, "stop_existing_windows_launchers", lambda: events.append("cleanup"))
    monkeypatch.setattr(cli, "sync_history_before_launch", lambda args: events.append("history-sync"))
    monkeypatch.setattr(cli, "maybe_print_update_notice", lambda: events.append("check-update"))
    monkeypatch.setattr(cli, "launch_and_inject", lambda *args: events.append("launch") or (FakeServer(), None))
    monkeypatch.setattr(cli, "wait_for_shutdown", lambda server, proc: events.append("wait"))

    exit_code = cli.main(["launch"])

    assert exit_code == 0
    assert events == ["cleanup", "history-sync", "check-update", "launch", "wait"]


def test_cli_update_notice_ignores_network_errors(monkeypatch, capsys):
    monkeypatch.setattr(cli.updater, "check_for_update", lambda: (_ for _ in ()).throw(RuntimeError("offline")))

    cli.maybe_print_update_notice()

    assert capsys.readouterr().out == ""


def test_cli_setup_alias_installs_with_default_launcher(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "install_codex_mate", lambda options: calls.append(options))

    exit_code = cli.main(["setup"])

    assert exit_code == 0
    assert len(calls) == 1
    assert calls[0].install_root is None
    assert calls[0].launcher_command is None


def test_cli_check_update_prints_latest_release(monkeypatch, capsys):
    class Release:
        version = "v1.1.1"
        url = "https://github.com/serein431/Codex-Mate/releases/tag/v1.1.1"
        body = "fixes"

    monkeypatch.setattr(cli.updater, "is_source_tree_mode", lambda: False)
    monkeypatch.setattr(cli.updater, "check_for_update", lambda: Release())

    exit_code = cli.main(["check-update"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "发现新版本 v1.1.1" in output
    assert "serein431/Codex-Mate/releases/tag/v1.1.1" in output


def test_cli_check_update_reports_current_version(monkeypatch, capsys):
    monkeypatch.setattr(cli.updater, "check_for_update", lambda: None)
    monkeypatch.setattr(cli.updater, "is_source_tree_mode", lambda: False)

    exit_code = cli.main(["check-update"])

    assert exit_code == 0
    assert "当前已是最新版本" in capsys.readouterr().out


def test_cli_check_update_reports_source_tree_migration_mode(monkeypatch, capsys):
    monkeypatch.setattr(cli.updater, "is_source_tree_mode", lambda: True)
    monkeypatch.setattr(cli.updater, "check_for_update", lambda: (_ for _ in ()).throw(AssertionError("should not check release version")))

    exit_code = cli.main(["check-update"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "源码目录运行" in output
    assert "update" in output


def test_cli_update_migrates_source_tree_to_release_install(monkeypatch, capsys):
    class Release:
        version = "v1.1.1"
        url = "https://github.com/serein431/Codex-Mate/releases/tag/v1.1.1"
        body = "fixes"
        asset_name = "CodexMate.zip"

    calls = []
    monkeypatch.setattr(cli.updater, "is_source_tree_mode", lambda: True)
    monkeypatch.setattr(cli.updater, "fetch_latest_release", lambda: Release())
    monkeypatch.setattr(cli.updater, "perform_update", lambda release: calls.append(release) or object())

    exit_code = cli.main(["update"])

    assert exit_code == 0
    assert calls[0].version == "v1.1.1"
    output = capsys.readouterr().out
    assert "源码目录运行" in output
    assert "迁移到 Release 安装" in output
    assert "更新完成" in output


def test_cli_update_installs_latest_release(monkeypatch, tmp_path, capsys):
    class Release:
        version = "v1.1.1"
        url = "https://github.com/serein431/Codex-Mate/releases/tag/v1.1.1"
        body = "fixes"

    calls = []
    monkeypatch.setattr(cli.updater, "is_source_tree_mode", lambda: False)
    monkeypatch.setattr(cli.updater, "check_for_update", lambda: Release())
    monkeypatch.setattr(cli.updater, "perform_update", lambda release: calls.append(release) or object())

    exit_code = cli.main(["update"])

    assert exit_code == 0
    assert calls[0].version == "v1.1.1"
    assert "更新完成" in capsys.readouterr().out


def test_cli_history_status_prints_json(monkeypatch, tmp_path, capsys):
    calls = []
    monkeypatch.setattr(cli.history_sync, "resolve_paths", lambda codex_home: calls.append(codex_home) or "paths")
    monkeypatch.setattr(cli.history_sync, "status", lambda paths: {"ok": True, "ready": True, "paths": paths})

    exit_code = cli.main(["history-status", "--codex-home", str(tmp_path), "--json"])

    assert exit_code == 0
    assert calls == [tmp_path]
    assert '"ready": true' in capsys.readouterr().out


def test_cli_history_sync_prints_json(monkeypatch, tmp_path, capsys):
    calls = []
    monkeypatch.setattr(cli.history_sync, "resolve_paths", lambda codex_home: calls.append(codex_home) or "paths")
    monkeypatch.setattr(cli.history_sync, "sync_history_to_current_profile", lambda paths: {"ok": True, "updated_database_rows": 2, "paths": paths})

    exit_code = cli.main(["history-sync", "--codex-home", str(tmp_path), "--json"])

    assert exit_code == 0
    assert calls == [tmp_path]
    assert '"updated_database_rows": 2' in capsys.readouterr().out


def test_cli_remove_alias_uninstalls_with_default_options(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "uninstall_codex_mate", lambda options: calls.append(options))

    exit_code = cli.main(["remove"])

    assert exit_code == 0
    assert len(calls) == 1
    assert calls[0].install_root is None
    assert calls[0].remove_data is False


def test_cli_logs_launch_failure_for_hidden_pythonw(monkeypatch, tmp_path):
    log_path = tmp_path / "codex-mate.log"
    monkeypatch.setattr(cli, "launch_and_inject", lambda *args: (_ for _ in ()).throw(RuntimeError("inject failed")))
    monkeypatch.setattr(cli, "launch_log_path", lambda: log_path)

    with pytest.raises(RuntimeError, match="inject failed"):
        cli.main(["launch"])

    assert "inject failed" in log_path.read_text(encoding="utf-8")


def test_cli_launch_failure_logging_is_best_effort(monkeypatch, tmp_path):
    log_path = tmp_path / "blocked" / "codex-mate.log"
    monkeypatch.setattr(cli, "launch_log_path", lambda: log_path)
    monkeypatch.setattr(type(log_path.parent), "mkdir", lambda *args, **kwargs: (_ for _ in ()).throw(PermissionError("blocked")))

    cli.log_launch_failure(RuntimeError("hidden failure"))
    cli.append_launch_warning("hidden warning")


def test_wait_for_shutdown_waits_for_windows_process_id(monkeypatch):
    server = FakeServer()
    waited = []
    monkeypatch.setattr(cli.sys, "platform", "win32")
    monkeypatch.setattr(cli.watcher, "find_codex_processes", lambda: [])
    monkeypatch.setattr(cli, "wait_for_windows_process_id", lambda process_id: waited.append(process_id))

    cli.wait_for_shutdown(server, 1234)

    assert waited == [1234]
    assert server.shutdown_called is True
    assert server.server_close_called is True


def test_wait_for_shutdown_keeps_windows_helper_alive_while_codex_processes_run(monkeypatch):
    server = FakeServer()
    states = iter([[1111], [1111], []])
    slept = []
    waited = []
    monkeypatch.setattr(cli.sys, "platform", "win32")
    monkeypatch.setattr(cli.watcher, "find_codex_processes", lambda: next(states))
    monkeypatch.setattr(cli.time, "sleep", lambda seconds: slept.append(seconds))
    monkeypatch.setattr(cli, "wait_for_windows_process_id", lambda process_id: waited.append(process_id))

    cli.wait_for_shutdown(server, 1234)

    assert slept == [2, 2]
    assert waited == []
    assert server.shutdown_called is True
    assert server.server_close_called is True


def test_wait_for_shutdown_tracks_macos_codex_processes(monkeypatch):
    server = FakeServer()
    states = iter([[111], []])
    slept = []
    monkeypatch.setattr(cli.sys, "platform", "darwin")
    monkeypatch.setattr(cli.watcher, "find_codex_processes", lambda: next(states))
    monkeypatch.setattr(cli.time, "sleep", lambda seconds: slept.append(seconds))

    cli.wait_for_shutdown(server, None)

    assert slept == [2]
    assert server.shutdown_called is True
    assert server.server_close_called is True


def test_wait_for_shutdown_waits_for_popen_like_process():
    server = FakeServer()
    proc = FakeProcess()

    cli.wait_for_shutdown(server, proc)

    assert proc.waited is True
    assert server.shutdown_called is True
    assert server.server_close_called is True
