"""Small bounded JSONL helpers for local telemetry files."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

DEFAULT_MAX_BYTES = 1024 * 1024


def _max_bytes() -> int:
    raw = os.environ.get("LIMA_TELEMETRY_JSONL_MAX_BYTES", str(DEFAULT_MAX_BYTES))
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_MAX_BYTES
    return max(value, 0)


def append_jsonl_record(
    path: Path,
    record: dict[str, Any],
    *,
    keep_lines: int,
    logger: logging.Logger,
    max_bytes: int | None = None,
) -> bool:
    """Append a compact JSONL record and trim the file if it grows too large."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=True, separators=(",", ":")) + "\n")
        _trim_jsonl(path, keep_lines=keep_lines, max_bytes=_max_bytes() if max_bytes is None else max_bytes)
        return True
    except Exception as exc:
        logger.warning("failed to append jsonl telemetry: %s", type(exc).__name__)
        return False


def _trim_jsonl(path: Path, *, keep_lines: int, max_bytes: int) -> None:
    if max_bytes <= 0:
        return
    try:
        if path.stat().st_size <= max_bytes:
            return
    except FileNotFoundError:
        return

    lines = path.read_text(encoding="utf-8").splitlines()
    kept = lines[-max(keep_lines, 1):]
    payload = "\n".join(kept)
    if payload:
        payload += "\n"
    path.write_text(payload, encoding="utf-8")
