import os
from pathlib import Path

from codex_mate import runtime


def test_runtime_command_args_use_module_in_source_mode(monkeypatch):
    monkeypatch.setattr(runtime.sys, "frozen", False, raising=False)
    monkeypatch.setattr(runtime.sys, "executable", "/opt/python/bin/python3")

    assert runtime.command_args("launch") == ["/opt/python/bin/python3", "-m", "codex_mate", "launch"]


def test_runtime_command_args_use_executable_in_frozen_mode(monkeypatch):
    monkeypatch.setattr(runtime.sys, "frozen", True, raising=False)
    monkeypatch.setattr(runtime.sys, "executable", "/Applications/CodexMate")

    assert runtime.command_args("launch") == ["/Applications/CodexMate", "launch"]


def test_runtime_command_args_prefer_pythonw_on_windows(monkeypatch, tmp_path):
    python = tmp_path / "python.exe"
    pythonw = tmp_path / "pythonw.exe"
    python.write_text("", encoding="utf-8")
    pythonw.write_text("", encoding="utf-8")
    monkeypatch.setattr(runtime.sys, "frozen", False, raising=False)
    monkeypatch.setattr(runtime.sys, "platform", "win32")
    monkeypatch.setattr(runtime.sys, "executable", str(python))

    assert runtime.command_args("watch", prefer_pythonw=True)[0] == str(pythonw)


def test_runtime_independent_child_env_resets_pyinstaller_onefile_child(monkeypatch):
    monkeypatch.setenv("_PYI_APPLICATION_HOME_DIR", r"C:\Users\ADMINI~1\AppData\Local\Temp\_MEI123")
    monkeypatch.setattr(runtime.sys, "frozen", True, raising=False)

    env = runtime.independent_child_env()

    assert env is not os.environ
    assert env["PYINSTALLER_RESET_ENVIRONMENT"] == "1"
    assert env["_PYI_APPLICATION_HOME_DIR"] == r"C:\Users\ADMINI~1\AppData\Local\Temp\_MEI123"


def test_runtime_independent_child_env_leaves_source_mode_alone(monkeypatch):
    monkeypatch.delenv("PYINSTALLER_RESET_ENVIRONMENT", raising=False)
    monkeypatch.setattr(runtime.sys, "frozen", False, raising=False)

    env = runtime.independent_child_env()

    assert "PYINSTALLER_RESET_ENVIRONMENT" not in env


def test_runtime_app_root_uses_executable_parent_when_frozen(monkeypatch, tmp_path):
    exe = tmp_path / "CodexMate"
    monkeypatch.setattr(runtime.sys, "frozen", True, raising=False)
    monkeypatch.setattr(runtime.sys, "executable", str(exe))

    assert runtime.app_root("/tmp/_MEI/codex_mate/runtime.py") == tmp_path


def test_runtime_app_root_uses_package_parent_in_source_mode(monkeypatch, tmp_path):
    package_file = tmp_path / "codex_mate" / "runtime.py"
    package_file.parent.mkdir()
    package_file.write_text("", encoding="utf-8")
    monkeypatch.setattr(runtime.sys, "frozen", False, raising=False)

    assert runtime.app_root(package_file) == tmp_path
