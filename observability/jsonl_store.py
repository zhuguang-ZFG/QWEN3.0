"""Small bounded JSONL helpers for local telemetry files.

AUDIT-5-O5：改为按大小滚动（rotate）而非重写整个文件，满足审计日志 append-only 要求。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from config import settings

_log = logging.getLogger(__name__)

DEFAULT_MAX_BYTES = 1024 * 1024
DEFAULT_BACKUP_COUNT = 5


def _max_bytes() -> int:
    raw = settings.OBSERVABILITY.telemetry_jsonl_max_bytes
    try:
        return max(int(raw), 0)
    except (TypeError, ValueError):
        return DEFAULT_MAX_BYTES


def _rotate_jsonl(path: Path, keep_backups: int = DEFAULT_BACKUP_COUNT) -> None:
    """Rotate jsonl files: path -> .1 -> .2 -> ... ; delete oldest if over limit."""
    if keep_backups <= 0:
        return
    # Remove oldest backup if it exists.
    oldest = path.parent / f"{path.name}.{keep_backups}"
    if oldest.exists():
        try:
            oldest.unlink()
        except OSError:
            pass
    # Shift existing backups upward.
    for i in range(keep_backups - 1, 0, -1):
        src = path.parent / f"{path.name}.{i}"
        dst = path.parent / f"{path.name}.{i + 1}"
        if src.exists():
            try:
                src.rename(dst)
            except OSError:
                pass
    # Rotate current file to .1
    if path.exists():
        try:
            path.rename(path.parent / f"{path.name}.1")
        except OSError:
            pass


def append_jsonl_record(
    path: Path,
    record: dict[str, Any],
    *,
    logger: logging.Logger,
    max_bytes: int | None = None,
) -> bool:
    """Append a compact JSONL record and rotate the file if it grows too large.

    The ``keep_lines`` argument is no longer used; rotation is size-based and append-only.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=True, separators=(",", ":")) + "\n")
        limit = _max_bytes() if max_bytes is None else max_bytes
        if limit > 0:
            try:
                if path.stat().st_size > limit:
                    _rotate_jsonl(path)
            except FileNotFoundError:
                pass
        return True
    except Exception as exc:
        logger.warning("failed to append jsonl telemetry: %s", type(exc).__name__)
        return False


def _backup_paths(path: Path, keep_backups: int = DEFAULT_BACKUP_COUNT) -> list[Path]:
    backups: list[Path] = []
    for i in range(1, keep_backups + 1):
        candidate = path.parent / f"{path.name}.{i}"
        if candidate.exists():
            backups.append(candidate)
        else:
            # Older backups won't exist if a gap appears; stop to avoid scanning.
            break
    return backups


def read_recent_jsonl_records(
    path: Path,
    limit: int,
    keep_backups: int = DEFAULT_BACKUP_COUNT,
) -> list[dict[str, Any]]:
    """Read the most recent JSONL records from the active file and backups."""
    if limit <= 0:
        limit = 1
    lines: list[str] = []
    # Active file is newest; .1 is next-newest, then .2, etc.
    # Read in chronological order (oldest backup first) so suffix returns latest.
    backups = _backup_paths(path, keep_backups)
    for source in list(reversed(backups)) + [path]:
        if not source.exists():
            continue
        try:
            lines.extend(source.read_text(encoding="utf-8").splitlines())
        except (OSError, UnicodeDecodeError) as exc:
            _log.warning("skipping unreadable telemetry file %s: %s", source, exc)
            continue

    records: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            records.append(parsed)
    return records
