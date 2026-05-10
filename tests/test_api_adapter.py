import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from codex_session_delete.api_adapter import ConfirmedHttpDeleteAdapter, UnavailableApiAdapter
from codex_session_delete.models import DeleteStatus, SessionRef


class DeleteHandler(BaseHTTPRequestHandler):
    calls = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        DeleteHandler.calls.append((self.path, payload))
        body = json.dumps({"ok": True}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


def test_unavailable_adapter_returns_none():
    adapter = UnavailableApiAdapter()

    assert adapter.delete(SessionRef(session_id="s1", title="First")) is None


def test_confirmed_http_adapter_posts_session_and_returns_server_deleted():
    DeleteHandler.calls = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), DeleteHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/delete-session"
        adapter = ConfirmedHttpDeleteAdapter(url)
        result = adapter.delete(SessionRef(session_id="s1", title="First"))
    finally:
        server.shutdown()
        thread.join(timeout=3)

    assert result is not None
    assert result.status == DeleteStatus.SERVER_DELETED
    assert result.session_id == "s1"
    assert DeleteHandler.calls == [("/delete-session", {"session_id": "s1", "title": "First"})]
