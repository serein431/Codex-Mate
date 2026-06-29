import json
import threading
from urllib.error import HTTPError
import urllib.request

from codex_mate.helper_server import HelperServer
from codex_mate.models import DeleteResult, DeleteStatus, SessionRef


class FakeDeleteService:
    def __init__(self):
        self.deleted = []
        self.undone = []
        self.archived_title_queries = []
        self.moved = []
        self.cc_switch_applied = []

    def delete(self, session: SessionRef):
        self.deleted.append(session)
        return DeleteResult(DeleteStatus.LOCAL_DELETED, session.session_id, "Deleted locally", undo_token="u1")

    def undo(self, token: str):
        self.undone.append(token)
        return DeleteResult(DeleteStatus.UNDONE, "s1", "Restored", undo_token=token)

    def find_archived_thread_by_title(self, title: str):
        self.archived_title_queries.append(title)
        return SessionRef(session_id="archived-t1", title=title)

    def check_update(self):
        return {"status": "available", "latest_version": "v9.9.9"}

    def update(self):
        return {"status": "updated", "latest_version": "v9.9.9"}

    def export_markdown(self, session: SessionRef):
        return {"status": "exported", "session_id": session.session_id, "message": "exported", "filename": "First.md", "markdown": "# First\n"}

    def backend_status(self):
        return {"status": "ok", "message": "后端已连接", "version": "v9.9.9"}

    def auth_enhancement_mode_status(self):
        return {"status": "ok", "auth_enhancement_mode": "loginPreserving"}

    def set_auth_enhancement_mode(self, mode: str):
        return {"status": "updated", "auth_enhancement_mode": mode}

    def provider_profile_status(self):
        return {"status": "ok", "profile": {"mode": "mixed-api", "api_key_present": True}}

    def apply_provider_profile(self, profile: dict[str, object]):
        return {"status": "updated", "profile": profile, "auth_enhancement_mode": "loginPreserving"}

    def cc_switch_providers(self):
        return {"status": "ok", "providers": [{"source_id": "p1", "name": "Relay"}]}

    def apply_cc_switch_provider(self, source_id: str):
        self.cc_switch_applied.append(source_id)
        return {
            "status": "updated",
            "source_id": source_id,
            "profile": {"provider": "jmrai"},
            "auth_enhancement_mode": "loginPreserving",
        }

    def move_thread_workspace(self, session: SessionRef, target_cwd: str):
        self.moved.append((session, target_cwd))
        return {"status": "moved", "session_id": session.session_id, "target_cwd": target_cwd}

    def move_thread_projectless(self, session: SessionRef):
        self.moved.append((session, ""))
        return {"status": "moved", "session_id": session.session_id, "target_cwd": ""}

    def thread_sort_key(self, session: SessionRef):
        return {"status": "ok", "session_id": session.session_id, "updated_at_ms": 1000}

    def thread_sort_keys(self, sessions: list[SessionRef]):
        return {"status": "ok", "sort_keys": [{"session_id": session.session_id, "updated_at_ms": index + 1} for index, session in enumerate(sessions)]}


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


def test_helper_server_routes_update_actions():
    service = FakeDeleteService()
    server = HelperServer("127.0.0.1", 0, service)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.port}"
        checked = post_json(base + "/check-update", {})
        updated = post_json(base + "/update", {})
    finally:
        server.shutdown()
        thread.join(timeout=3)

    assert checked["status"] == "available"
    assert updated["status"] == "updated"


def test_helper_server_routes_export_and_backend_status():
    service = FakeDeleteService()
    server = HelperServer("127.0.0.1", 0, service)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.port}"
        exported = post_json(base + "/export-markdown", {"session_id": "s1", "title": "First"})
        status = post_json(base + "/backend/status", {})
    finally:
        server.shutdown()
        thread.join(timeout=3)

    assert exported["status"] == "exported"
    assert exported["filename"] == "First.md"
    assert status["status"] == "ok"
    assert status["message"] == "后端已连接"


def test_helper_server_does_not_route_conversation_timeline():
    service = FakeDeleteService()
    server = HelperServer("127.0.0.1", 0, service)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.port}"
        try:
            post_json(base + "/conversation-timeline", {"session_id": "s1", "title": "First"})
        except HTTPError as exc:
            status = exc.code
            body = json.loads(exc.read().decode("utf-8"))
        else:
            raise AssertionError("conversation timeline route should be removed")
    finally:
        server.shutdown()
        thread.join(timeout=3)

    assert status == 404
    assert body == {"error": "not found"}


def test_helper_server_routes_auth_enhancement_mode():
    service = FakeDeleteService()
    server = HelperServer("127.0.0.1", 0, service)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.port}"
        status = post_json(base + "/auth-enhancement-mode/status", {})
        updated = post_json(base + "/auth-enhancement-mode/set", {"mode": "forceInject"})
    finally:
        server.shutdown()
        thread.join(timeout=3)

    assert status == {"status": "ok", "auth_enhancement_mode": "loginPreserving"}
    assert updated == {"status": "updated", "auth_enhancement_mode": "forceInject"}


def test_helper_server_routes_provider_profile():
    service = FakeDeleteService()
    server = HelperServer("127.0.0.1", 0, service)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.port}"
        status = post_json(base + "/provider-profile/status", {})
        applied = post_json(
            base + "/provider-profile/apply",
            {
                "profile": {
                    "mode": "mixed-api",
                    "provider": "jmrai",
                    "base_url": "https://jmrai.example/v1",
                    "api_key": "sk-new",
                    "model": "gpt-5.5",
                    "wire_api": "responses",
                }
            },
        )
    finally:
        server.shutdown()
        thread.join(timeout=3)

    assert status["profile"]["mode"] == "mixed-api"
    assert applied["status"] == "updated"


def test_helper_server_routes_cc_switch_provider_actions():
    service = FakeDeleteService()
    server = HelperServer("127.0.0.1", 0, service)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.port}"
        providers = post_json(base + "/cc-switch/providers", {})
        applied = post_json(base + "/cc-switch/apply", {"source_id": "p1"})
    finally:
        server.shutdown()
        thread.join(timeout=3)

    assert providers["providers"] == [{"source_id": "p1", "name": "Relay"}]
    assert applied["status"] == "updated"
    assert applied["source_id"] == "p1"
    assert applied["profile"]["provider"] == "jmrai"
    assert applied["auth_enhancement_mode"] == "loginPreserving"
    assert service.cc_switch_applied == ["p1"]


def test_helper_server_routes_session_move_and_sort_keys():
    service = FakeDeleteService()
    server = HelperServer("127.0.0.1", 0, service)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.port}"
        moved = post_json(base + "/move-thread-workspace", {"session_id": "s1", "title": "First", "target_cwd": "/work/project"})
        projectless = post_json(base + "/move-thread-projectless", {"session_id": "s2", "title": "Second"})
        sort_key = post_json(base + "/thread-sort-key", {"session_id": "s1", "title": "First"})
        sort_keys = post_json(base + "/thread-sort-keys", {"sessions": [{"session_id": "s1"}, {"session_id": "s2"}]})
    finally:
        server.shutdown()
        thread.join(timeout=3)

    assert moved == {"status": "moved", "session_id": "s1", "target_cwd": "/work/project"}
    assert projectless == {"status": "moved", "session_id": "s2", "target_cwd": ""}
    assert sort_key["updated_at_ms"] == 1000
    assert sort_keys["sort_keys"] == [{"session_id": "s1", "updated_at_ms": 1}, {"session_id": "s2", "updated_at_ms": 2}]
    assert service.moved[0][0].session_id == "s1"
    assert service.moved[0][1] == "/work/project"
    assert service.moved[1][0].session_id == "s2"


def test_helper_server_rejects_removed_file_tree_actions():
    service = FakeDeleteService()
    server = HelperServer("127.0.0.1", 0, service)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.port}"
        try:
            post_json(base + "/file-tree/roots", {"thread_id": "local:t1"})
        except HTTPError as exc:
            assert exc.code == 404
        else:
            raise AssertionError("file tree endpoint should be removed")
    finally:
        server.shutdown()
        thread.join(timeout=3)


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
