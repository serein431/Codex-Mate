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
