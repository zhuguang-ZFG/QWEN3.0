"""SQLite-backed persistence for admin client API keys.

P3-16: Client keys were previously stored only in memory and lost on restart.
This module persists them to a dedicated SQLite table under LIMA_DATA_DIR.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

from config.db_config import LIMA_DATA_DIR
from config.sqlite_pool import pooled_sqlite_conn

_log = logging.getLogger(__name__)
_lock = threading.RLock()


def _db_path() -> str:
    if _DB_PATH_OVERRIDE:
        return _DB_PATH_OVERRIDE
    data_dir = Path(LIMA_DATA_DIR)
    data_dir.mkdir(parents=True, exist_ok=True)
    return str(data_dir / "client_keys.db")


_DB_PATH_OVERRIDE: str | None = None


@contextmanager
def _pooled_conn() -> Generator[sqlite3.Connection, None, None]:
    """Yield a pooled connection with sqlite3.Row enabled; resets it on return."""
    with pooled_sqlite_conn(_db_path(), check_same_thread=False) as conn:
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS client_keys (
                    key_id TEXT PRIMARY KEY,
                    key_masked TEXT NOT NULL,
                    label TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    quota_daily INTEGER NOT NULL DEFAULT 1000,
                    quota_monthly INTEGER NOT NULL DEFAULT 30000,
                    usage_daily INTEGER NOT NULL DEFAULT 0,
                    usage_monthly INTEGER NOT NULL DEFAULT 0,
                    rate_limit_rpm INTEGER NOT NULL DEFAULT 20,
                    allowed_urls TEXT NOT NULL DEFAULT '[\"*\"]',
                    last_used_at REAL NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL DEFAULT 0
                )
                """
            )
            yield conn
        finally:
            conn.row_factory = None


def load_keys() -> dict[str, dict[str, Any]]:
    """Load all client keys from SQLite into the in-memory dict format."""
    try:
        with _pooled_conn() as conn:
            rows = conn.execute("SELECT * FROM client_keys").fetchall()
    except (sqlite3.Error, OSError) as exc:
        _log.warning("Failed to load client keys from SQLite: %s", exc, exc_info=True)
        return {}

    keys: dict[str, dict[str, Any]] = {}
    for row in rows:
        entry = dict(row)
        entry["enabled"] = bool(entry["enabled"])
        entry["allowed_urls"] = json.loads(entry["allowed_urls"])
        keys[entry["key_id"]] = entry
    return keys


def save_key(entry: dict[str, Any]) -> None:
    """Upsert a single client key."""
    with _lock:
        try:
            with _pooled_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO client_keys (key_id, key_masked, label, enabled, quota_daily,
                        quota_monthly, usage_daily, usage_monthly, rate_limit_rpm, allowed_urls,
                        last_used_at, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(key_id) DO UPDATE SET
                        key_masked=excluded.key_masked,
                        label=excluded.label,
                        enabled=excluded.enabled,
                        quota_daily=excluded.quota_daily,
                        quota_monthly=excluded.quota_monthly,
                        usage_daily=excluded.usage_daily,
                        usage_monthly=excluded.usage_monthly,
                        rate_limit_rpm=excluded.rate_limit_rpm,
                        allowed_urls=excluded.allowed_urls,
                        last_used_at=excluded.last_used_at,
                        created_at=excluded.created_at
                    """,
                    (
                        entry["key_id"],
                        entry["key_masked"],
                        entry["label"],
                        int(entry["enabled"]),
                        int(entry["quota_daily"]),
                        int(entry["quota_monthly"]),
                        int(entry["usage_daily"]),
                        int(entry["usage_monthly"]),
                        int(entry["rate_limit_rpm"]),
                        json.dumps(entry.get("allowed_urls", ["*"])),
                        float(entry["last_used_at"]),
                        float(entry["created_at"]),
                    ),
                )
        except (sqlite3.Error, OSError) as exc:
            _log.warning("Failed to persist client key %s: %s", entry.get("key_id"), exc, exc_info=True)


def record_usage(key_id: str, tokens: int = 0) -> None:
    """Increment usage counters for a client key and update last_used_at."""
    with _lock:
        try:
            with _pooled_conn() as conn:
                conn.execute(
                    """
                    UPDATE client_keys
                    SET usage_daily = usage_daily + 1,
                        usage_monthly = usage_monthly + 1,
                        last_used_at = ?
                    WHERE key_id = ?
                    """,
                    (time.time(), key_id),
                )
                conn.commit()
        except (sqlite3.Error, OSError) as exc:
            _log.warning("Failed to record usage for client key %s: %s", key_id, exc, exc_info=True)


def get_key(key_id: str) -> dict[str, Any] | None:
    """Load a single key from persistence."""
    with _lock:
        try:
            with _pooled_conn() as conn:
                row = conn.execute("SELECT * FROM client_keys WHERE key_id = ?", (key_id,)).fetchone()
                if row is None:
                    return None
                entry = dict(row)
                entry["enabled"] = bool(entry["enabled"])
                entry["allowed_urls"] = json.loads(entry["allowed_urls"])
                return entry
        except (sqlite3.Error, OSError) as exc:
            _log.warning("Failed to load client key %s: %s", key_id, exc, exc_info=True)
            return None


def delete_key(key_id: str) -> None:
    """Delete a client key from persistence."""
    with _lock:
        try:
            with _pooled_conn() as conn:
                conn.execute("DELETE FROM client_keys WHERE key_id = ?", (key_id,))
        except (sqlite3.Error, OSError) as exc:
            _log.warning("Failed to delete client key %s: %s", key_id, exc, exc_info=True)


def set_db_path_for_tests(path: str) -> None:
    """Override the SQLite path in tests."""
    global _DB_PATH_OVERRIDE
    _DB_PATH_OVERRIDE = path
