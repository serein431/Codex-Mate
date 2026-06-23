from __future__ import annotations

import sqlite3
from pathlib import Path


SQLITE_EXTENSIONS = {".db", ".sqlite", ".sqlite3"}
ROLLOUT_DIR_NAMES = ("sessions", "archived_sessions")


def default_codex_home() -> Path:
    return Path.home() / ".codex"


def legacy_thread_db_path(codex_home: str | Path | None = None) -> Path:
    home = Path(codex_home).expanduser() if codex_home is not None else default_codex_home()
    return home / "state_5.sqlite"


def discover_thread_db_paths(codex_home: str | Path | None = None) -> list[Path]:
    home = Path(codex_home).expanduser() if codex_home is not None else default_codex_home()
    paths: list[Path] = []
    sqlite_dir = home / "sqlite"
    if sqlite_dir.exists():
        for path in sorted(sqlite_dir.iterdir(), key=lambda item: item.name):
            if path.is_file() and path.suffix in SQLITE_EXTENSIONS and has_table(path, "threads"):
                paths.append(path)
    legacy = legacy_thread_db_path(home)
    if legacy.exists() and has_table(legacy, "threads") and legacy not in paths:
        paths.append(legacy)
    return paths


def primary_thread_db_path(codex_home: str | Path | None = None) -> Path:
    home = Path(codex_home).expanduser() if codex_home is not None else default_codex_home()
    discovered = discover_thread_db_paths(home)
    return discovered[0] if discovered else legacy_thread_db_path(home)


def codex_home_for_db_path(db_path: str | Path | None) -> Path | None:
    if db_path is None:
        return None
    path = Path(db_path).expanduser()
    parent = path.parent
    if parent.name == "sqlite":
        return parent.parent
    return parent


def rollout_dirs(codex_home: str | Path | None = None) -> list[Path]:
    home = Path(codex_home).expanduser() if codex_home is not None else default_codex_home()
    return [home / name for name in ROLLOUT_DIR_NAMES if (home / name).exists()]


def has_table(path: Path, table: str) -> bool:
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
            return db.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1",
                (table,),
            ).fetchone() is not None
    except sqlite3.Error:
        return False
