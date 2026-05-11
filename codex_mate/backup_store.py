from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any


class BackupStore:
    def __init__(self, backup_dir: Path):
        self.backup_dir = backup_dir
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def write_backup(self, session_id: str, source_db: str, tables: dict[str, list[dict[str, Any]]]) -> str:
        token = f"{int(time.time())}-{uuid.uuid4().hex}"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        path = self.path_for(token)
        payload = {
            "token": token,
            "session_id": session_id,
            "source_db": source_db,
            "tables": tables,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return token

    def read_backup(self, token: str) -> dict[str, Any]:
        path = self.path_for(token)
        if not path.exists():
            raise FileNotFoundError(f"Backup token not found: {token}")
        return json.loads(path.read_text(encoding="utf-8"))

    def path_for(self, token: str) -> Path:
        safe = "".join(ch for ch in token if ch.isalnum() or ch in "-_")
        return self.backup_dir / f"{safe}.json"
