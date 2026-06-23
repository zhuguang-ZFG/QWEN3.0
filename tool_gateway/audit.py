"""Tool gateway audit — event recording with optional SQLite persistence."""

import json
import logging
import os
import threading
import time

from config import settings
from config.sqlite_pool import pooled_sqlite_conn

_log = logging.getLogger(__name__)

_lock = threading.Lock()
_events: list[dict] = []
_SENSITIVE_KEYS = (
    "api_key",
    "apikey",
    "authorization",
    "body",
    "cookie",
    "key",
    "message",
    "messages",
    "password",
    "prompt",
    "secret",
    "token",
)


def _db_path() -> str:
    return settings.DB.tool_audit_db


from observability.events import _sanitize_text


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(token in lowered for token in _SENSITIVE_KEYS)


def _sanitize_value(value: object) -> object:
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if _is_sensitive_key(str(key)) else _sanitize_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value[:50]]
    if isinstance(value, tuple):
        return tuple(_sanitize_value(item) for item in value[:50])
    if isinstance(value, str):
        return _sanitize_text(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return _sanitize_text(value)


# ── In-memory audit ─────────────────────────────────────────────────────────


def audit_event(event_type: str, **kwargs) -> dict:
    event: dict = _sanitize_value({"time": int(time.time()), "event": event_type, **kwargs})  # type: ignore[assignment]
    with _lock:
        _events.append(event)
        if len(_events) > 1000:
            _events[:] = _events[-500:]
    _persist_event(event)
    return event


# ── SQLite persistence ──────────────────────────────────────────────────────


def _ensure_schema(conn) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            tool TEXT DEFAULT '',
            reason TEXT DEFAULT '',
            details TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_events(timestamp DESC)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_type ON audit_events(event_type, timestamp DESC)
    """)


def _persist_event(event: dict) -> None:
    try:
        db_path = _db_path()
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        with pooled_sqlite_conn(db_path) as conn:
            _ensure_schema(conn)
            conn.execute(
                "INSERT INTO audit_events (timestamp, event_type, tool, reason, details) VALUES (?, ?, ?, ?, ?)",
                (
                    event.get("time", 0),
                    event.get("event", ""),
                    event.get("tool", ""),
                    event.get("reason", ""),
                    json.dumps({k: v for k, v in event.items() if k not in ("time", "event", "tool", "reason")}),
                ),
            )
    except Exception as exc:
        _log.warning(
            "tool audit persist failed event=%s: %s",
            event.get("event", ""),
            type(exc).__name__,
        )


# ── Query ───────────────────────────────────────────────────────────────────


def get_recent_events(limit: int = 50) -> list[dict]:
    with _lock:
        return list(_events[-limit:])


def query_events(
    event_type: str = "",
    tool: str = "",
    limit: int = 50,
) -> list[dict]:
    db_path = _db_path()
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conditions = []
    params = []
    if event_type:
        conditions.append("event_type = ?")
        params.append(event_type)
    if tool:
        conditions.append("tool = ?")
        params.append(tool)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    with pooled_sqlite_conn(db_path) as conn:
        _ensure_schema(conn)
        rows = conn.execute(
            f"SELECT timestamp, event_type, tool, reason, details "
            f"FROM audit_events {where} ORDER BY timestamp DESC LIMIT ?",
            params + [limit],
        ).fetchall()
    return [
        {"time": r[0], "event": r[1], "tool": r[2], "reason": r[3], "details": json.loads(r[4]) if r[4] else {}}
        for r in rows
    ]


def count_events(event_type: str = "", tool: str = "") -> int:
    db_path = _db_path()
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conditions = []
    params = []
    if event_type:
        conditions.append("event_type = ?")
        params.append(event_type)
    if tool:
        conditions.append("tool = ?")
        params.append(tool)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    with pooled_sqlite_conn(db_path) as conn:
        _ensure_schema(conn)
        count = conn.execute(f"SELECT COUNT(*) FROM audit_events {where}", params).fetchone()[0]
    return count


# ── Reset ───────────────────────────────────────────────────────────────────


def reset_audit() -> None:
    with _lock:
        _events.clear()
    try:
        db_path = _db_path()
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        with pooled_sqlite_conn(db_path) as conn:
            _ensure_schema(conn)
            conn.execute("DELETE FROM audit_events")
    except Exception as exc:
        _log.warning("tool audit reset failed: %s", type(exc).__name__)
