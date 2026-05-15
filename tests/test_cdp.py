import json
import websocket

from codex_mate import __version__
from codex_mate import cdp
from codex_mate.cdp import BRIDGE_BINDING_NAME, _bridge_loop, add_script_to_new_document, build_bridge_script, make_bridge_binding_name, pick_page_target, runtime_evaluate


class TimeoutThenMessageSocket:
    def __init__(self):
        self.recv_count = 0
        self.sent = []

    def recv(self):
        self.recv_count += 1
        if self.recv_count == 1:
            raise websocket.WebSocketTimeoutException("idle")
        if self.recv_count == 2:
            return json.dumps({
                "method": "Runtime.bindingCalled",
                "params": {"payload": json.dumps({"id": "1", "path": "/diagnostic", "payload": {"session_id": "s1"}})},
            })
        raise RuntimeError("stop after response")

    def send(self, payload):
        self.sent.append(payload)


class IdResponseSocket:
    def __init__(self):
        self.sent = []

    def send(self, payload):
        self.sent.append(json.loads(payload))

    def recv(self):
        message_id = self.sent[-1]["id"]
        return json.dumps({"id": message_id, "result": {}})


def test_pick_page_target_prefers_codex_title():
    targets = [
        {"type": "background_page", "title": "bg", "webSocketDebuggerUrl": "ws://bg"},
        {"type": "page", "title": "Codex", "url": "app://codex", "webSocketDebuggerUrl": "ws://page"},
    ]

    assert pick_page_target(targets)["webSocketDebuggerUrl"] == "ws://page"


def test_pick_page_target_rejects_missing_websocket():
    try:
        pick_page_target([{"type": "page", "title": "Codex"}])
    except RuntimeError as exc:
        assert "No injectable" in str(exc)
    else:
        raise AssertionError("target without websocket was accepted")


def test_build_bridge_script_installs_binding_callbacks():
    script = build_bridge_script("codexMate")

    assert "window.codexMate" in script
    assert "window.__codexMateResolve" in script
    assert "window.__codexMateReject" in script


def test_bridge_binding_name_is_versioned_for_reinjection():
    assert BRIDGE_BINDING_NAME == "codexMateV2"


def test_loopback_session_ignores_environment_proxies():
    session = cdp._loopback_session()
    try:
        assert session.trust_env is False
    finally:
        session.close()


def test_make_bridge_binding_name_is_unique_for_reinjection():
    first = make_bridge_binding_name()
    second = make_bridge_binding_name()

    assert first.startswith("codexMateV2_")
    assert second.startswith("codexMateV2_")
    assert first != second


def test_bridge_loop_continues_after_idle_timeout():
    ws = TimeoutThenMessageSocket()

    _bridge_loop(ws, lambda path, payload: {"status": "ok", "path": path})

    assert ws.recv_count == 3
    assert "__codexMateResolve" in ws.sent[0]


def test_persistent_script_helpers_register_reload_and_current_document_injection():
    ws = IdResponseSocket()

    add_script_to_new_document(ws, 1, "window.__probe = true")
    runtime_evaluate(ws, 2, "window.__probe = true")

    assert ws.sent[0]["method"] == "Page.addScriptToEvaluateOnNewDocument"
    assert ws.sent[0]["params"]["source"] == "window.__probe = true"
    assert ws.sent[1]["method"] == "Runtime.evaluate"
    assert ws.sent[1]["params"]["expression"] == "window.__probe = true"


def test_inject_file_prefixes_helper_and_package_version(monkeypatch, tmp_path):
    script_path = tmp_path / "renderer.js"
    script_path.write_text("window.__rendererLoaded = true;", encoding="utf-8")
    evaluated = []

    monkeypatch.setattr(
        cdp,
        "list_targets",
        lambda port: [{"type": "page", "title": "Codex", "url": "app://codex", "webSocketDebuggerUrl": "ws://page"}],
    )
    monkeypatch.setattr(cdp, "evaluate_script", lambda websocket_url, script: evaluated.append((websocket_url, script)) or {"result": {}})

    result = cdp.inject_file(9229, script_path, 57321)

    assert result == {"result": {}}
    assert evaluated[0][0] == "ws://page"
    assert f"window.__CODEX_MATE_HELPER__ = \"http://127.0.0.1:57321\";" in evaluated[0][1]
    assert f"window.__CODEX_MATE_VERSION__ = {json.dumps(__version__)};" in evaluated[0][1]
    assert evaluated[0][1].endswith("window.__rendererLoaded = true;")
