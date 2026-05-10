import plistlib
from pathlib import Path

from codex_session_delete import autostart


LEGACY_BRAND = "Codex" + "++"
LEGACY_OWNER = "Big" + "Pizza" + "V3"
LEGACY_PROJECT = "Codex" + "Plus" + "Plus"


def test_build_macos_launch_agent_plist_runs_watcher_with_python(tmp_path):
    plist = autostart.build_macos_launch_agent_plist(
        python_executable=Path("/opt/python/bin/python3"),
        debug_port=9333,
    )

    assert plist["Label"] == "dev.codexmate.watcher"
    assert plist["ProgramArguments"] == [
        "/opt/python/bin/python3",
        "-m",
        "codex_session_delete",
        "watch",
        "--debug-port",
        "9333",
    ]
    assert plist["RunAtLoad"] is True
    assert plist["KeepAlive"] is True
    assert plist["WorkingDirectory"] == str(autostart.project_root())
    assert "watcher.launchd.log" in plist["StandardOutPath"]
    assert "watcher.launchd.err" in plist["StandardErrorPath"]


def test_build_macos_launch_agent_plist_sets_working_directory(tmp_path):
    plist = autostart.build_macos_launch_agent_plist(
        python_executable=Path("/opt/python/bin/python3"),
        debug_port=9333,
        working_directory=tmp_path,
    )

    assert plist["WorkingDirectory"] == str(tmp_path)


def test_write_macos_launch_agent_creates_valid_plist(tmp_path, monkeypatch):
    monkeypatch.setattr(autostart.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(autostart.sys, "executable", "/usr/local/bin/python3")

    path = autostart.write_macos_launch_agent(debug_port=9229)

    assert path == tmp_path / "Library" / "LaunchAgents" / "dev.codexmate.watcher.plist"
    decoded = plistlib.loads(path.read_bytes())
    assert decoded["ProgramArguments"][:3] == ["/usr/local/bin/python3", "-m", "codex_session_delete"]
    assert decoded["ProgramArguments"][-1] == "9229"
    assert decoded["WorkingDirectory"] == str(autostart.project_root())


def test_build_windows_watcher_install_script_registers_run_and_startup_shortcut():
    script = autostart.build_windows_watcher_install_script(debug_port=9444)

    assert "CodexMateWatcher" in script
    assert "CodexMateWatcher.lnk" in script
    assert LEGACY_BRAND not in script
    assert LEGACY_OWNER not in script
    assert LEGACY_PROJECT not in script
    assert "-m codex_session_delete watch --debug-port 9444" in script
    assert "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run" in script
    assert "Startup" in script


def test_cli_watch_install_uses_autostart_module(monkeypatch):
    from codex_session_delete import cli

    calls = []
    monkeypatch.setattr(cli.autostart, "install_watcher_autostart", lambda debug_port: calls.append(debug_port))

    assert cli.main(["watch-install", "--debug-port", "9555"]) == 0
    assert calls == [9555]


def test_cli_watch_remove_uses_autostart_module(monkeypatch):
    from codex_session_delete import cli

    calls = []
    monkeypatch.setattr(cli.autostart, "uninstall_watcher_autostart", lambda: calls.append("remove"))

    assert cli.main(["watch-remove"]) == 0
    assert calls == ["remove"]
