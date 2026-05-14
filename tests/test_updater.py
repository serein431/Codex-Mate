import json
from pathlib import Path

import pytest
import requests

from codex_mate import updater


def test_parse_version_tag_accepts_v_prefix_and_suffix():
    assert updater.parse_version_tag("v1.2.3") == (1, 2, 3)
    assert updater.parse_version_tag("1.2.3") == (1, 2, 3)
    assert updater.parse_version_tag("v1.2.3-beta.1") == (1, 2, 3)


def test_is_newer_version_compares_numeric_segments():
    assert updater.is_newer_version("v1.1.1", "1.1.0") is True
    assert updater.is_newer_version("v1.1.0", "1.1.0") is False
    assert updater.is_newer_version("v1.0.9", "1.1.0") is False


def test_release_from_github_payload_selects_wheel_asset():
    release = updater.Release.from_github_payload(
        {
            "tag_name": "v1.1.1",
            "html_url": "https://github.com/serein431/Codex-Mate/releases/tag/v1.1.1",
            "body": "fixes",
            "prerelease": False,
            "draft": False,
            "assets": [
                {"name": "CodexMate.zip", "browser_download_url": "https://example.test/source.zip"},
                {"name": "codex_mate-1.1.1-py3-none-any.whl", "browser_download_url": "https://example.test/pkg.whl"},
            ],
        }
    )

    assert release.version == "v1.1.1"
    assert release.asset_name == "codex_mate-1.1.1-py3-none-any.whl"
    assert release.asset_url == "https://example.test/pkg.whl"


def test_release_from_github_payload_prefers_source_zip_over_platform_installers():
    release = updater.Release.from_github_payload(
        {
            "tag_name": "v1.1.7",
            "html_url": "https://github.com/serein431/Codex-Mate/releases/tag/v1.1.7",
            "body": "fixes",
            "assets": [
                {"name": "CodexMate-windows.zip", "browser_download_url": "https://example.test/windows.zip"},
                {"name": "CodexMate-macos.zip", "browser_download_url": "https://example.test/macos.zip"},
                {"name": "CodexMate.zip", "browser_download_url": "https://example.test/source.zip"},
            ],
        }
    )

    assert release.asset_name == "CodexMate.zip"
    assert release.asset_url == "https://example.test/source.zip"


def test_fetch_latest_release_uses_github_api(monkeypatch):
    requested = []

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "tag_name": "v1.1.1",
                "html_url": "https://github.com/serein431/Codex-Mate/releases/tag/v1.1.1",
                "assets": [],
            }

    monkeypatch.setattr(updater.requests, "get", lambda url, **kwargs: requested.append((url, kwargs)) or Response())

    release = updater.fetch_latest_release()

    assert release.version == "v1.1.1"
    assert requested[0][0] == updater.DEFAULT_RELEASE_API_URL
    assert requested[0][1]["timeout"] == 10
    assert "Codex Mate" in requested[0][1]["headers"]["User-Agent"]


def test_fetch_latest_release_reports_rate_limit(monkeypatch):
    class Response:
        status_code = 403
        text = "API rate limit exceeded"

        def raise_for_status(self):
            raise requests.HTTPError("403 Client Error", response=self)

    monkeypatch.setattr(updater.requests, "get", lambda *args, **kwargs: Response())

    with pytest.raises(updater.UpdateError, match="GitHub 更新检查暂时被限流"):
        updater.fetch_latest_release()


def test_download_asset_writes_release_file(monkeypatch, tmp_path):
    class Response:
        headers = {"content-length": "7"}

        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size):
            yield b"abc"
            yield b"defg"

    monkeypatch.setattr(updater.requests, "get", lambda *args, **kwargs: Response())

    path = updater.download_asset("https://example.test/pkg.whl", "pkg.whl", tmp_path)

    assert path == tmp_path / "pkg.whl"
    assert path.read_bytes() == b"abcdefg"


def test_update_python_executable_uses_console_python_for_pythonw(monkeypatch, tmp_path):
    pythonw = tmp_path / "pythonw.exe"
    python = tmp_path / "python.exe"
    pythonw.write_text("", encoding="utf-8")
    python.write_text("", encoding="utf-8")
    monkeypatch.setattr(updater.sys, "platform", "win32")

    assert updater.update_python_executable(str(pythonw)) == str(python)


def test_update_python_executable_keeps_pythonw_without_console_python(monkeypatch, tmp_path):
    pythonw = tmp_path / "pythonw.exe"
    pythonw.write_text("", encoding="utf-8")
    monkeypatch.setattr(updater.sys, "platform", "win32")

    assert updater.update_python_executable(str(pythonw)) == str(pythonw)


def test_update_python_executable_keeps_non_windows_pythonw(monkeypatch, tmp_path):
    pythonw = tmp_path / "pythonw.exe"
    python = tmp_path / "python.exe"
    pythonw.write_text("", encoding="utf-8")
    python.write_text("", encoding="utf-8")
    monkeypatch.setattr(updater.sys, "platform", "linux")

    assert updater.update_python_executable(str(pythonw)) == str(pythonw)


def test_perform_update_installs_downloaded_wheel_and_reruns_setup(monkeypatch, tmp_path):
    commands = []
    release = updater.Release(
        version="v1.1.1",
        url="https://github.com/serein431/Codex-Mate/releases/tag/v1.1.1",
        body="fixes",
        asset_name="pkg.whl",
        asset_url="https://example.test/pkg.whl",
    )
    wheel = tmp_path / "pkg.whl"
    wheel.write_bytes(b"wheel")
    monkeypatch.setattr(updater, "download_asset", lambda *args: wheel)
    monkeypatch.setattr(updater.autostart, "windows_watcher_autostart_installed", lambda: False)
    monkeypatch.setattr(updater.autostart, "macos_watcher_autostart_installed", lambda: False)
    monkeypatch.setattr(updater.subprocess, "run", lambda command, **kwargs: commands.append((command, kwargs)))

    result = updater.perform_update(release, python_executable="python.exe", download_dir=tmp_path)

    assert result.installed_path == wheel
    assert commands == [
        (["python.exe", "-m", "pip", "install", "--upgrade", str(wheel)], {"check": True}),
        (["python.exe", "-m", "codex_mate", "setup"], {"check": True, "cwd": updater.safe_setup_cwd()}),
    ]


def test_perform_update_uses_console_python_when_started_by_pythonw(monkeypatch, tmp_path):
    commands = []
    release = updater.Release(
        version="v1.1.1",
        url="https://github.com/serein431/Codex-Mate/releases/tag/v1.1.1",
        body="fixes",
        asset_name="pkg.whl",
        asset_url="https://example.test/pkg.whl",
    )
    wheel = tmp_path / "pkg.whl"
    wheel.write_bytes(b"wheel")
    pythonw = tmp_path / "pythonw.exe"
    python = tmp_path / "python.exe"
    pythonw.write_text("", encoding="utf-8")
    python.write_text("", encoding="utf-8")
    monkeypatch.setattr(updater.sys, "platform", "win32")
    monkeypatch.setattr(updater, "download_asset", lambda *args: wheel)
    monkeypatch.setattr(updater.autostart, "windows_watcher_autostart_installed", lambda: False)
    monkeypatch.setattr(updater.autostart, "macos_watcher_autostart_installed", lambda: False)
    monkeypatch.setattr(updater.subprocess, "run", lambda command, **kwargs: commands.append((command, kwargs)))

    updater.perform_update(release, python_executable=str(pythonw), download_dir=tmp_path)

    assert commands == [
        ([str(python), "-m", "pip", "install", "--upgrade", str(wheel)], {"check": True}),
        ([str(python), "-m", "codex_mate", "setup"], {"check": True, "cwd": updater.safe_setup_cwd()}),
    ]


def test_perform_update_restores_windows_watcher_when_it_was_enabled(monkeypatch, tmp_path):
    commands = []
    release = updater.Release(
        version="v1.1.1",
        url="https://github.com/serein431/Codex-Mate/releases/tag/v1.1.1",
        body="fixes",
        asset_name="pkg.whl",
        asset_url="https://example.test/pkg.whl",
    )
    wheel = tmp_path / "pkg.whl"
    wheel.write_bytes(b"wheel")
    monkeypatch.setattr(updater, "download_asset", lambda *args: wheel)
    monkeypatch.setattr(updater.autostart, "windows_watcher_autostart_installed", lambda: True)
    monkeypatch.setattr(updater.subprocess, "run", lambda command, **kwargs: commands.append((command, kwargs)))

    updater.perform_update(release, python_executable="python.exe", download_dir=tmp_path)

    assert commands[-1] == (["python.exe", "-m", "codex_mate", "watch-install"], {"check": True, "cwd": updater.safe_setup_cwd()})


def test_perform_update_restores_macos_watcher_when_it_was_enabled(monkeypatch, tmp_path):
    commands = []
    release = updater.Release(
        version="v1.1.1",
        url="https://github.com/serein431/Codex-Mate/releases/tag/v1.1.1",
        body="fixes",
        asset_name="pkg.whl",
        asset_url="https://example.test/pkg.whl",
    )
    wheel = tmp_path / "pkg.whl"
    wheel.write_bytes(b"wheel")
    monkeypatch.setattr(updater.sys, "platform", "darwin")
    monkeypatch.setattr(updater, "download_asset", lambda *args: wheel)
    monkeypatch.setattr(updater.autostart, "windows_watcher_autostart_installed", lambda: False)
    monkeypatch.setattr(updater.autostart, "macos_watcher_autostart_installed", lambda: True, raising=False)
    monkeypatch.setattr(updater.subprocess, "run", lambda command, **kwargs: commands.append((command, kwargs)))

    updater.perform_update(release, python_executable="/opt/python/bin/python3", download_dir=tmp_path)

    assert commands[-1] == (["/opt/python/bin/python3", "-m", "codex_mate", "watch-install"], {"check": True, "cwd": updater.safe_setup_cwd()})


def test_perform_update_rejects_release_without_asset(tmp_path):
    release = updater.Release(version="v1.1.1", url="https://example.test", body="")

    with pytest.raises(updater.UpdateError, match="没有可下载的 Release asset"):
        updater.perform_update(release, python_executable="python.exe", download_dir=tmp_path)


def test_source_tree_root_detects_git_clone_project(tmp_path):
    project = tmp_path / "CodexMate"
    package = project / "codex_mate"
    package.mkdir(parents=True)
    (project / ".git").mkdir()
    (project / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    module_file = package / "updater.py"
    module_file.write_text("", encoding="utf-8")

    assert updater.source_tree_root(module_file) == project


def test_source_tree_root_ignores_non_source_install(tmp_path):
    package = tmp_path / "site-packages" / "codex_mate"
    package.mkdir(parents=True)
    module_file = package / "updater.py"
    module_file.write_text("", encoding="utf-8")

    assert updater.source_tree_root(module_file) is None


def test_check_for_update_skips_source_tree_mode(monkeypatch, tmp_path):
    project = tmp_path / "CodexMate"
    package = project / "codex_mate"
    package.mkdir(parents=True)
    (project / ".git").mkdir()
    (project / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    module_file = package / "updater.py"
    module_file.write_text("", encoding="utf-8")
    fetched = []
    monkeypatch.setattr(updater, "PACKAGE_MODULE_FILE", module_file)
    monkeypatch.setattr(updater, "fetch_latest_release", lambda: fetched.append(True))

    assert updater.check_for_update() is None
    assert fetched == []
