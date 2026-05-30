from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Protocol

from codex_mate.models import DeleteResult, DeleteStatus, SessionRef


class DeleteService(Protocol):
    def delete(self, session: SessionRef) -> DeleteResult: ...
    def undo(self, token: str) -> DeleteResult: ...
    def find_archived_thread_by_title(self, title: str) -> SessionRef | None: ...
    def export_markdown(self, session: SessionRef) -> dict[str, object]: ...
    def conversation_timeline(self, session: SessionRef) -> dict[str, object]: ...
    def check_update(self) -> dict[str, object]: ...
    def update(self) -> dict[str, object]: ...
    def backend_status(self) -> dict[str, object]: ...
    def auth_enhancement_mode_status(self) -> dict[str, object]: ...
    def set_auth_enhancement_mode(self, mode: str) -> dict[str, object]: ...
    def provider_profile_status(self) -> dict[str, object]: ...
    def apply_provider_profile(self, profile: dict[str, object]) -> dict[str, object]: ...
    def cc_switch_providers(self) -> dict[str, object]: ...
    def apply_cc_switch_provider(self, source_id: str) -> dict[str, object]: ...
    def move_thread_workspace(self, session: SessionRef, target_cwd: str) -> dict[str, object]: ...
    def move_thread_projectless(self, session: SessionRef) -> dict[str, object]: ...
    def thread_sort_key(self, session: SessionRef) -> dict[str, object]: ...
    def thread_sort_keys(self, sessions: list[SessionRef]) -> dict[str, object]: ...


class HelperServer(ThreadingHTTPServer):
    def __init__(self, host: str, port: int, service: DeleteService):
        self.service = service
        super().__init__((host, port), _Handler)

    @property
    def port(self) -> int:
        return int(self.server_address[1])


class _Handler(BaseHTTPRequestHandler):
    server: HelperServer

    def do_OPTIONS(self) -> None:
        self._send_json({"ok": True})

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json({"ok": True})
            return
        self._send_json({"error": "not found"}, status=404)

    def do_POST(self) -> None:
        try:
            payload = self._read_json()
            if self.path == "/delete":
                session = SessionRef(session_id=str(payload.get("session_id", "")), title=str(payload.get("title", "")))
                self._send_json(self.server.service.delete(session).to_dict())
                return
            if self.path == "/undo":
                token = str(payload.get("undo_token", ""))
                self._send_json(self.server.service.undo(token).to_dict())
                return
            if self.path == "/archived-thread":
                session = self.server.service.find_archived_thread_by_title(str(payload.get("title", "")))
                self._send_json({"session_id": session.session_id, "title": session.title} if session else {"session_id": "", "title": ""})
                return
            if self.path == "/export-markdown":
                session = SessionRef(session_id=str(payload.get("session_id", "")), title=str(payload.get("title", "")))
                self._send_json(self.server.service.export_markdown(session))
                return
            if self.path == "/conversation-timeline":
                session = SessionRef(session_id=str(payload.get("session_id", "")), title=str(payload.get("title", "")))
                self._send_json(self.server.service.conversation_timeline(session))
                return
            if self.path == "/move-thread-workspace":
                session = SessionRef(session_id=str(payload.get("session_id", "")), title=str(payload.get("title", "")))
                self._send_json(self.server.service.move_thread_workspace(session, str(payload.get("target_cwd", ""))))
                return
            if self.path == "/move-thread-projectless":
                session = SessionRef(session_id=str(payload.get("session_id", "")), title=str(payload.get("title", "")))
                self._send_json(self.server.service.move_thread_projectless(session))
                return
            if self.path == "/thread-sort-key":
                session = SessionRef(session_id=str(payload.get("session_id", "")), title=str(payload.get("title", "")))
                self._send_json(self.server.service.thread_sort_key(session))
                return
            if self.path == "/thread-sort-keys":
                raw_sessions = payload.get("sessions", [])
                sessions = [
                    SessionRef(session_id=str(item.get("session_id", "")), title=str(item.get("title", "")))
                    for item in raw_sessions
                    if isinstance(item, dict) and item.get("session_id")
                ] if isinstance(raw_sessions, list) else []
                self._send_json(self.server.service.thread_sort_keys(sessions))
                return
            if self.path == "/check-update":
                self._send_json(self.server.service.check_update())
                return
            if self.path == "/update":
                self._send_json(self.server.service.update())
                return
            if self.path == "/backend/status":
                self._send_json(self.server.service.backend_status())
                return
            if self.path == "/auth-enhancement-mode/status":
                self._send_json(self.server.service.auth_enhancement_mode_status())
                return
            if self.path == "/auth-enhancement-mode/set":
                self._send_json(self.server.service.set_auth_enhancement_mode(str(payload.get("mode", ""))))
                return
            if self.path == "/provider-profile/status":
                self._send_json(self.server.service.provider_profile_status())
                return
            if self.path == "/provider-profile/apply":
                raw_profile = payload.get("profile", {})
                profile = raw_profile if isinstance(raw_profile, dict) else {}
                self._send_json(self.server.service.apply_provider_profile(profile))
                return
            if self.path == "/cc-switch/providers":
                self._send_json(self.server.service.cc_switch_providers())
                return
            if self.path == "/cc-switch/apply":
                self._send_json(self.server.service.apply_cc_switch_provider(str(payload.get("source_id", ""))))
                return
            self._send_json({"error": "not found"}, status=404)
        except Exception as exc:
            result = DeleteResult(DeleteStatus.FAILED, str(payload.get("session_id", "")) if "payload" in locals() else "", str(exc))
            self._send_json(result.to_dict(), status=400)

    def log_message(self, format: str, *args: object) -> None:
        return

    def _read_json(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        return json.loads(raw)

    def _send_json(self, payload: dict[str, object], status: int = 200) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
