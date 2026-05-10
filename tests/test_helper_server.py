import json
import threading
import urllib.request

from codex_session_delete.helper_server import HelperServer
from codex_session_delete.models import DeleteResult, DeleteStatus, SessionRef


class FakeDeleteService:
    def __init__(self):
        self.deleted = []
        self.undone = []
        self.archived_title_queries = []

    def delete(self, session: SessionRef):
        self.deleted.append(session)
        return DeleteResult(DeleteStatus.LOCAL_DELETED, session.session_id, "Deleted locally", undo_token="u1")

    def undo(self, token: str):
        self.undone.append(token)
        return DeleteResult(DeleteStatus.UNDONE, "s1", "Restored", undo_token=token)

    def find_archived_thread_by_title(self, title: str):
        self.archived_title_queries.append(title)
        return SessionRef(session_id="archived-t1", title=title)


def post_json(url, payload):
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=3) as response:
        return json.loads(response.read().decode("utf-8"))


def test_helper_server_delete_and_undo():
    service = FakeDeleteService()
    server = HelperServer("127.0.0.1", 0, service)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.port}"
        deleted = post_json(base + "/delete", {"session_id": "s1", "title": "First"})
        undone = post_json(base + "/undo", {"undo_token": "u1"})
    finally:
        server.shutdown()
        thread.join(timeout=3)

    assert deleted["status"] == "local_deleted"
    assert deleted["undo_token"] == "u1"
    assert undone["status"] == "undone"
    assert service.deleted[0].session_id == "s1"
    assert service.undone == ["u1"]


def test_helper_server_resolves_archived_thread_by_title():
    service = FakeDeleteService()
    server = HelperServer("127.0.0.1", 0, service)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.port}"
        resolved = post_json(base + "/archived-thread", {"title": "Codex Thread"})
    finally:
        server.shutdown()
        thread.join(timeout=3)

    assert resolved == {"session_id": "archived-t1", "title": "Codex Thread"}
    assert service.archived_title_queries == ["Codex Thread"]


def test_helper_server_allows_private_network_preflight():
    service = FakeDeleteService()
    server = HelperServer("127.0.0.1", 0, service)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.port}/delete",
            method="OPTIONS",
            headers={
                "Origin": "file://",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
                "Access-Control-Request-Private-Network": "true",
            },
        )
        with urllib.request.urlopen(request, timeout=3) as response:
            private_network = response.headers.get("Access-Control-Allow-Private-Network")
    finally:
        server.shutdown()
        thread.join(timeout=3)

    assert private_network == "true"
