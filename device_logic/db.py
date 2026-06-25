"""SQLite connection and schema bootstrap for LiMa device app data."""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from config.db_config import get_lima_db_path
from config.sqlite_pool import pooled_sqlite_conn
from device_logic.db_migrations import apply_migrations as _apply_migrations

_schema_lock = threading.Lock()
_schema_ready_paths: set[str] = set()


def db_path() -> Path:
    return Path(get_lima_db_path())


def _run_migrations(conn: sqlite3.Connection) -> None:
    _apply_migrations(conn)


def ensure_schema(conn: sqlite3.Connection, resolved_path: str) -> None:
    with _schema_lock:
        if resolved_path in _schema_ready_paths:
            return
        schema_path = Path(__file__).resolve().parent.parent / "migrations" / "xiaozhi_schema.sql"
        if not schema_path.exists():
            raise RuntimeError(f"xiaozhi schema missing: {schema_path}")
        conn.executescript(schema_path.read_text(encoding="utf-8"))
        _run_migrations(conn)
        _schema_ready_paths.add(resolved_path)


@contextmanager
def connect() -> Generator[sqlite3.Connection, None, None]:
    """Yield a SQLite connection from the thread-local pool.

    The connection is automatically returned to the pool after the context.
    """
    path = db_path()
    if path.parent != Path(""):
        path.parent.mkdir(parents=True, exist_ok=True)
    with pooled_sqlite_conn(str(path), check_same_thread=False) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        ensure_schema(conn, str(path.resolve()))
        try:
            yield conn
        finally:
            conn.row_factory = None
