"""Thread-local SQLite connection pool.

Reduces connection churn for modules that open/close SQLite on every operation.
Connections are cached per thread and closed when the thread dies. Callers still
own transaction boundaries via context managers.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from contextlib import contextmanager
from typing import Generator

_log = logging.getLogger(__name__)


class _ConnectionPool:
    """Simple thread-local connection cache."""

    def __init__(self, max_per_thread: int = 3) -> None:
        self._max_per_thread = max(max_per_thread, 1)
        self._local = threading.local()

    def _pool(self) -> dict[str, list[sqlite3.Connection]]:
        if not hasattr(self._local, "conns"):
            self._local.conns = {}
        return self._local.conns

    def get(self, path: str, *, check_same_thread: bool = False) -> sqlite3.Connection:
        pool = self._pool()
        available = pool.get(path)
        if available:
            conn = available.pop()
            try:
                conn.execute("SELECT 1")
                return conn
            except sqlite3.Error:
                try:
                    conn.close()
                except Exception as exc:
                    # Best-effort close of a possibly broken connection; safe to ignore.
                    _log.warning("sqlite_pool close of stale connection failed: %s", exc)
        return sqlite3.connect(path, check_same_thread=check_same_thread)

    def put(self, path: str, conn: sqlite3.Connection) -> None:
        pool = self._pool()
        if len(pool.get(path, [])) < self._max_per_thread:
            pool.setdefault(path, []).append(conn)
        else:
            try:
                conn.close()
            except Exception as exc:
                # Best-effort close when pool is full; safe to ignore.
                _log.warning("sqlite_pool close of overflow connection failed: %s", exc)

    def clear(self) -> None:
        """Close all cached connections in the current thread."""
        for path, conns in list(getattr(self._local, "conns", {}).items()):
            for conn in conns:
                try:
                    conn.close()
                except Exception as exc:
                    # Best-effort close during bulk cleanup; safe to ignore.
                    _log.warning("sqlite_pool bulk close failed for %s: %s", path, exc)
        self._local.conns = {}


_POOL = _ConnectionPool()


class _PooledConnectionProxy:
    """Transparent proxy that returns the connection to the pool on close()."""

    def __init__(self, path: str, conn: sqlite3.Connection) -> None:
        object.__setattr__(self, "_pool_path", path)
        object.__setattr__(self, "_conn", conn)

    def __getattribute__(self, name: str):
        if name in ("close", "_pool_path", "_conn"):
            return object.__getattribute__(self, name)
        return getattr(object.__getattribute__(self, "_conn"), name)

    def __setattr__(self, name: str, value) -> None:
        setattr(self._conn, name, value)

    def close(self) -> None:
        pool_release(self._pool_path, self._conn)


def get_pooled_connection(path: str, *, check_same_thread: bool = False) -> sqlite3.Connection:
    """Return a pooled connection proxy.

    Callers can use this as a drop-in replacement for sqlite3.connect(path):
    conn.execute(...); conn.commit(); conn.close() recycles the connection.

    Note: the returned object is a proxy, not an actual sqlite3.Connection.
    Code that does isinstance(conn, sqlite3.Connection) will get False.
    """
    conn = _POOL.get(path, check_same_thread=check_same_thread)
    return _PooledConnectionProxy(path, conn)  # type: ignore[return-value]


@contextmanager
def pooled_sqlite_conn(
    path: str,
    *,
    check_same_thread: bool = False,
) -> Generator[sqlite3.Connection, None, None]:
    """Yield a SQLite connection from the thread-local pool.

    Commits on normal exit, rolls back on exception. The connection is returned
    to the pool (or closed if the pool is full).
    """
    conn = _POOL.get(path, check_same_thread=check_same_thread)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _POOL.put(path, conn)


def sqlite_connect_pooled(path: str, *, check_same_thread: bool = False) -> sqlite3.Connection:
    """Get a pooled connection without context-manager lifecycle.

    Caller must call `pool_release(path, conn)` when done.
    """
    return _POOL.get(path, check_same_thread=check_same_thread)


def pool_release(path: str, conn: sqlite3.Connection) -> None:
    """Return a connection acquired via `sqlite_connect_pooled`."""
    _POOL.put(path, conn)


def pool_clear() -> None:
    """Close all pooled connections in the current thread (for tests)."""
    _POOL.clear()
