from codex_session_delete import __main__


def test_package_main_delegates_to_cli_main(monkeypatch):
    calls = []
    monkeypatch.setattr(__main__.cli, "main", lambda: calls.append(True) or 0)

    assert __main__.main() == 0
    assert calls == [True]
