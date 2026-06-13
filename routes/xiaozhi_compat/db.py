"""SQLite connection and schema bootstrap for XiaoZhi v1 compat."""

from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path

_schema_lock = threading.Lock()
_schema_ready_paths: set[str] = set()


def db_path() -> Path:
    return Path(os.environ.get("LIMA_DB_PATH", "data/lima.db"))


def ensure_schema(conn: sqlite3.Connection, resolved_path: str) -> None:
    with _schema_lock:
        if resolved_path in _schema_ready_paths:
            return
        schema_path = Path(__file__).resolve().parent.parent.parent / "migrations" / "xiaozhi_schema.sql"
        if not schema_path.exists():
            raise RuntimeError(f"xiaozhi schema missing: {schema_path}")
        conn.executescript(schema_path.read_text(encoding="utf-8"))
        conn.commit()
        _schema_ready_paths.add(resolved_path)


def connect() -> sqlite3.Connection:
    path = db_path()
    if path.parent != Path(""):
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    ensure_schema(conn, str(path.resolve()))
    return conn
