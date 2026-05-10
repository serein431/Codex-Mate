from __future__ import annotations

from typing import Protocol

import requests

from codex_session_delete.models import DeleteResult, DeleteStatus, SessionRef


class ApiAdapter(Protocol):
    def delete(self, session: SessionRef) -> DeleteResult | None: ...


class UnavailableApiAdapter:
    def delete(self, session: SessionRef) -> DeleteResult | None:
        return None


class ConfirmedHttpDeleteAdapter:
    def __init__(self, delete_url: str):
        self.delete_url = delete_url

    def delete(self, session: SessionRef) -> DeleteResult | None:
        response = requests.post(
            self.delete_url,
            json={"session_id": session.session_id, "title": session.title},
            timeout=5,
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return DeleteResult(
            DeleteStatus.SERVER_DELETED,
            session.session_id,
            "已通过服务器接口删除",
        )
