from __future__ import annotations

import json
import os
import threading
import uuid
from pathlib import Path
from typing import Callable

import requests
import websocket


BridgeHandler = Callable[[str, dict[str, object]], dict[str, object]]
BRIDGE_BINDING_NAME = "codexMateV2"


def list_targets(port: int) -> list[dict[str, object]]:
    response = requests.get(f"http://127.0.0.1:{port}/json", timeout=3)
    response.raise_for_status()
    return response.json()


def pick_page_target(targets: list[dict[str, object]]) -> dict[str, object]:
    pages = [target for target in targets if target.get("type") == "page" and target.get("webSocketDebuggerUrl")]
    for target in pages:
        title = str(target.get("title", ""))
        url = str(target.get("url", ""))
        if "codex" in (title + " " + url).lower():
            return target
    if pages:
        return pages[0]
    raise RuntimeError("No injectable Codex page target found")


def evaluate_script(websocket_url: str, script: str) -> dict[str, object]:
    ws = websocket.create_connection(websocket_url, timeout=5)
    try:
        add_script_to_new_document(ws, 1, script)
        return runtime_evaluate(ws, 2, script)
    finally:
        ws.close()


def build_bridge_script(binding_name: str) -> str:
    return f"""
(() => {{
  window.__codexMateCallbacks = new Map();
  window.__codexMateSeq = 0;
  window.__codexMateResolve = (id, result) => {{
    const callback = window.__codexMateCallbacks.get(id);
    if (!callback) return;
    window.__codexMateCallbacks.delete(id);
    callback.resolve(result);
  }};
  window.__codexMateReject = (id, message) => {{
    const callback = window.__codexMateCallbacks.get(id);
    if (!callback) return;
    window.__codexMateCallbacks.delete(id);
    callback.resolve({{ status: "failed", message }});
  }};
  window.__codexMateBridge = (path, payload) => new Promise((resolve) => {{
    const id = String(++window.__codexMateSeq);
    window.__codexMateCallbacks.set(id, {{ resolve }});
    window.{binding_name}(JSON.stringify({{ id, path, payload }}));
  }});
}})();
"""


def make_bridge_binding_name() -> str:
    return f"{BRIDGE_BINDING_NAME}_{os.getpid()}_{uuid.uuid4().hex}"


def install_bridge(websocket_url: str, binding_name: str, handler: BridgeHandler) -> websocket.WebSocket:
    ws = websocket.create_connection(websocket_url, timeout=5)
    ws.send(json.dumps({"id": 1, "method": "Runtime.addBinding", "params": {"name": binding_name}}))
    _wait_for_id(ws, 1)
    script = build_bridge_script(binding_name)
    add_script_to_new_document(ws, 2, script)
    runtime_evaluate(ws, 3, script)
    thread = threading.Thread(target=_bridge_loop, args=(ws, handler), daemon=True)
    thread.start()
    return ws


def inject_file(port: int, script_path: Path, helper_port: int, handler: BridgeHandler | None = None) -> websocket.WebSocket | dict[str, object]:
    targets = list_targets(port)
    target = pick_page_target(targets)
    websocket_url = str(target["webSocketDebuggerUrl"])
    bridge_socket = install_bridge(websocket_url, make_bridge_binding_name(), handler) if handler else None
    script = script_path.read_text(encoding="utf-8")
    prefix = f"window.__CODEX_MATE_HELPER__ = 'http://127.0.0.1:{helper_port}';\n"
    result = evaluate_script(websocket_url, prefix + script)
    return bridge_socket or result

def _bridge_loop(ws: websocket.WebSocket, handler: BridgeHandler) -> None:
    while True:
        try:
            message = json.loads(ws.recv())
        except websocket.WebSocketTimeoutException:
            continue
        except Exception:
            return
        if message.get("method") != "Runtime.bindingCalled":
            continue
        params = message.get("params", {})
        try:
            payload = json.loads(str(params.get("payload", "{}")))
            request_id = str(payload["id"])
            result = handler(str(payload["path"]), dict(payload.get("payload", {})))
            _resolve_bridge(ws, request_id, result)
        except Exception as exc:
            request_id = str(locals().get("payload", {}).get("id", ""))
            if request_id:
                _reject_bridge(ws, request_id, str(exc))


def _resolve_bridge(ws: websocket.WebSocket, request_id: str, result: dict[str, object]) -> None:
    expression = f"window.__codexMateResolve({json.dumps(request_id)}, {json.dumps(result)})"
    ws.send(json.dumps({"id": _next_id(), "method": "Runtime.evaluate", "params": {"expression": expression, "awaitPromise": False, "allowUnsafeEvalBlockedByCSP": True}}))


def _reject_bridge(ws: websocket.WebSocket, request_id: str, message: str) -> None:
    expression = f"window.__codexMateReject({json.dumps(request_id)}, {json.dumps(message)})"
    ws.send(json.dumps({"id": _next_id(), "method": "Runtime.evaluate", "params": {"expression": expression, "awaitPromise": False, "allowUnsafeEvalBlockedByCSP": True}}))


def add_script_to_new_document(ws: websocket.WebSocket, message_id: int, script: str) -> dict[str, object]:
    ws.send(
        json.dumps(
            {
                "id": message_id,
                "method": "Page.addScriptToEvaluateOnNewDocument",
                "params": {"source": script},
            }
        )
    )
    return _wait_for_id(ws, message_id)


def runtime_evaluate(ws: websocket.WebSocket, message_id: int, script: str) -> dict[str, object]:
    ws.send(
        json.dumps(
            {
                "id": message_id,
                "method": "Runtime.evaluate",
                "params": {"expression": script, "awaitPromise": False, "allowUnsafeEvalBlockedByCSP": True},
            }
        )
    )
    return _wait_for_id(ws, message_id)


def _wait_for_id(ws: websocket.WebSocket, message_id: int) -> dict[str, object]:
    while True:
        message = json.loads(ws.recv())
        if message.get("id") == message_id:
            if "error" in message:
                raise RuntimeError(str(message["error"]))
            return message


_id_lock = threading.Lock()
_id = 100


def _next_id() -> int:
    global _id
    with _id_lock:
        _id += 1
        return _id
