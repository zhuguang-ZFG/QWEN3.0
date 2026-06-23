"""Activation codes persisted in LIMA SQLite (multi-worker safe)."""

from __future__ import annotations

import logging
import secrets
import sqlite3
import threading
import time

from config import settings

_log = logging.getLogger(__name__)

ACTIVATION_TTL_SECONDS = 600
_table_lock = threading.Lock()


def _connect():
    from device_logic.db import connect

    return connect()


def _ensure_table(conn: sqlite3.Connection) -> None:
    # ponytail: always IF NOT EXISTS — _table_ready per-process cache breaks isolated test DBs.
    with _table_lock:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS v2_activation_code (
                code TEXT PRIMARY KEY,
                mac_address TEXT NOT NULL DEFAULT '',
                expires_at REAL NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_v2_activation_expires ON v2_activation_code(expires_at)")
        conn.commit()


def _purge_expired(conn: sqlite3.Connection, now_ts: float) -> None:
    conn.execute("DELETE FROM v2_activation_code WHERE expires_at <= ?", (now_ts,))


def check_activation_code(code: str) -> bool:
    now_ts = time.time()
    with _connect() as conn:
        _ensure_table(conn)
        _purge_expired(conn, now_ts)
        row = conn.execute(
            "SELECT 1 FROM v2_activation_code WHERE code=? AND expires_at > ?",
            (code, now_ts),
        ).fetchone()
        if row is not None:
            # ponytail: consume the code immediately — one-time use, prevents replay within TTL.
            conn.execute("DELETE FROM v2_activation_code WHERE code=?", (code,))
            conn.commit()
            return True
        conn.commit()
    expected = settings.DEVICE.activation_code
    if expected:
        return secrets.compare_digest(code, expected)
    _log.warning("LIMA_XIAOZHI_ACTIVATION_CODE is not configured; rejecting unissued activation code")
    return False


def new_activation_code(mac_address: str = "") -> str:
    now_ts = time.time()
    expires_at = now_ts + ACTIVATION_TTL_SECONDS
    with _connect() as conn:
        _ensure_table(conn)
        _purge_expired(conn, now_ts)
        while True:
            code = f"{secrets.randbelow(1_000_000):06d}"
            exists = conn.execute("SELECT 1 FROM v2_activation_code WHERE code=?", (code,)).fetchone()
            if exists is None:
                break
        conn.execute(
            "INSERT INTO v2_activation_code (code, mac_address, expires_at) VALUES (?, ?, ?)",
            (code, mac_address or "", expires_at),
        )
        conn.commit()
        return code


def reset_activation_store_for_tests() -> None:
    with _connect() as conn:
        _ensure_table(conn)
        conn.execute("DELETE FROM v2_activation_code")
        conn.commit()
