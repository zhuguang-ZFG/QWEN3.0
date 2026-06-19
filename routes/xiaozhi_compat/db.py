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


def _run_migrations(conn: sqlite3.Connection) -> None:
    """Idempotent migrations for existing databases."""
    # Ensure password_hash column exists on legacy v2_account tables.
    columns = {row[1] for row in conn.execute("PRAGMA table_info(v2_account)")}
    if "password_hash" not in columns:
        conn.execute("ALTER TABLE v2_account ADD COLUMN password_hash TEXT")

    # Ensure v2_captcha table exists (CREATE TABLE IF NOT EXISTS is already idempotent,
    # but we keep this here for clarity and to apply any future index changes).
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS v2_captcha (
            id              TEXT PRIMARY KEY,
            code            TEXT NOT NULL,
            expires_at      TEXT NOT NULL,
            created_at      TEXT DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_v2_captcha_expires ON v2_captcha(expires_at)")
    conn.commit()


def ensure_schema(conn: sqlite3.Connection, resolved_path: str) -> None:
    with _schema_lock:
        if resolved_path in _schema_ready_paths:
            return
        schema_path = Path(__file__).resolve().parent.parent.parent / "migrations" / "xiaozhi_schema.sql"
        if not schema_path.exists():
            raise RuntimeError(f"xiaozhi schema missing: {schema_path}")
        conn.executescript(schema_path.read_text(encoding="utf-8"))
        _run_migrations(conn)
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
