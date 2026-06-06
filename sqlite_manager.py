"""Unified SQLite connection manager with WAL mode and busy_timeout.

Usage:
    from sqlite_manager import get_connection

    conn = get_connection("data/my_store.db")
    conn.execute("SELECT 1")

All connections share these defaults:
- journal_mode = WAL (write-ahead logging for concurrent reads)
- busy_timeout = 30000ms (wait 30s instead of immediate "database is locked")
- check_same_thread = False (safe for FastAPI async contexts)
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

_log = logging.getLogger(__name__)

DEFAULT_BUSY_TIMEOUT = 30_000  # 30 seconds
_connections: dict[str, sqlite3.Connection] = {}


def get_connection(
    db_path: str | Path,
    *,
    busy_timeout: int = DEFAULT_BUSY_TIMEOUT,
    wal: bool = True,
) -> sqlite3.Connection:
    """Return a cached, properly configured SQLite connection.

    Connections are keyed by resolved path and reused across calls.
    Safe for single-process multi-thread FastAPI deployments.
    """
    key = str(Path(db_path).resolve()) if db_path != ":memory:" else ":memory:"

    if key in _connections:
        try:
            _connections[key].execute("SELECT 1")
            return _connections[key]
        except sqlite3.Error:
            _log.debug("sqlite_manager: stale connection for %s, reconnecting", key)
            del _connections[key]

    conn = sqlite3.connect(key, check_same_thread=False, timeout=busy_timeout / 1000)

    if wal and key != ":memory:":
        conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(f"PRAGMA busy_timeout={busy_timeout}")

    _connections[key] = conn
    _log.debug("sqlite_manager: opened connection for %s (wal=%s, timeout=%dms)", key, wal, busy_timeout)
    return conn


def close_all() -> int:
    """Close all cached connections. Call during graceful shutdown. Returns count closed."""
    count = 0
    for key, conn in list(_connections.items()):
        try:
            conn.close()
            count += 1
        except sqlite3.Error as exc:
            _log.warning("sqlite_manager: close failed for %s: %s", key, exc)
    _connections.clear()
    return count


def reset(db_path: str | Path | None = None) -> None:
    """Close specific or all connections (test helper)."""
    if db_path is None:
        close_all()
    else:
        key = str(Path(db_path).resolve())
        conn = _connections.pop(key, None)
        if conn:
            try:
                conn.close()
            except sqlite3.Error:
                pass
