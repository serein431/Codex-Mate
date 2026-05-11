from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Iterable

from codex_mate import __version__


MAX_TEXT_BYTES = 512 * 1024
LOG_NAMES = (
    "launcher.log",
    "watcher.log",
    "watcher.stdout.log",
    "watcher.stderr.log",
    "watcher.launchd.log",
    "watcher.launchd.err",
)
SECRET_PATTERNS = (
    re.compile(r"(sk-[A-Za-z0-9_\-]{8,})"),
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]{8,}"),
    re.compile(r"(?i)(api[_-]?key\s*[=:]\s*)['\"]?[^'\"\s]+['\"]?"),
    re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[A-Za-z0-9._\-]{8,}"),
    re.compile(r"(?i)(token\s*[=:]\s*)['\"]?[^'\"\s]+['\"]?"),
)


def data_root() -> Path:
    return Path.home() / ".codex-mate"


def default_codex_home() -> Path:
    return Path.home() / ".codex"


def append_log(component: str, message: str, *, level: str = "INFO", data_root: Path | None = None) -> None:
    root = data_root or globals()["data_root"]()
    path = root / f"{component}.log"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().isoformat(timespec="seconds")
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"[{timestamp}] [{level.upper()}] {message.rstrip()}\n")
    except OSError:
        pass


def redact_text(text: str) -> str:
    redacted = text
    for pattern in SECRET_PATTERNS:
        if pattern.pattern.startswith("(?i)(bearer") or pattern.pattern.startswith("(?i)(api") or pattern.pattern.startswith("(?i)(authorization") or pattern.pattern.startswith("(?i)(token"):
            redacted = pattern.sub(lambda match: match.group(1) + "[REDACTED]", redacted)
        else:
            redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def safe_read_text(path: Path, max_bytes: int = MAX_TEXT_BYTES) -> str:
    try:
        data = path.read_bytes()
    except OSError as exc:
        return f"Unable to read {path}: {exc}\n"
    suffix = ""
    if len(data) > max_bytes:
        data = data[-max_bytes:]
        suffix = "\n[Codex Mate: file truncated to the last 512 KiB]\n"
    return suffix + data.decode("utf-8", errors="replace")


def write_text(bundle: zipfile.ZipFile, name: str, text: str) -> None:
    bundle.writestr(name, redact_text(text))


def iter_existing_logs(root: Path) -> Iterable[tuple[str, Path]]:
    for name in LOG_NAMES:
        path = root / name
        if path.exists():
            yield f"logs/{name}", path


def run_process_snapshot() -> str:
    if sys.platform == "win32":
        command = [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "Get-CimInstance Win32_Process | "
            "Where-Object { $_.Name -match 'Codex|CodexMate|python' -or $_.CommandLine -match 'codex_mate|CodexMate' } | "
            "Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Depth 3",
        ]
    else:
        command = ["ps", "ax", "-o", "pid=,ppid=,command="]
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=6,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return f"process snapshot failed: {exc}\n"
    output = result.stdout or ""
    if result.stderr:
        output += "\n[stderr]\n" + result.stderr
    return output


def summary_text(root: Path, codex_home: Path) -> str:
    payload = {
        "codex_mate_version": __version__,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "platform": sys.platform,
        "platform_detail": platform.platform(),
        "python": sys.version.replace("\n", " "),
        "executable": sys.executable,
        "frozen": bool(getattr(sys, "frozen", False)),
        "data_root": str(root),
        "codex_home": str(codex_home),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def collect_diagnostics(
    output_path: Path | None = None,
    *,
    data_root: Path | None = None,
    codex_home: Path | None = None,
) -> Path:
    root = data_root or globals()["data_root"]()
    codex_dir = codex_home or default_codex_home()
    if output_path is None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_path = root / "diagnostics" / f"CodexMate-diagnostics-{stamp}.zip"
    output_path = output_path.expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        write_text(bundle, "summary.txt", summary_text(root, codex_dir))
        write_text(bundle, "processes.txt", run_process_snapshot())
        for archive_name, path in iter_existing_logs(root):
            write_text(bundle, archive_name, safe_read_text(path))

        config_path = codex_dir / "config.toml"
        if config_path.exists():
            write_text(bundle, "codex/config.toml", safe_read_text(config_path))

        state_path = codex_dir / ".codex-global-state.json"
        if state_path.exists():
            write_text(bundle, "codex/.codex-global-state.json", safe_read_text(state_path))

    append_log("support", f"diagnostic bundle created: {output_path}", data_root=root)
    return output_path
