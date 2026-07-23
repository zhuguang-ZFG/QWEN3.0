"""Per-device DLC API token issuance and shared lookup (v2_device_token)."""

from __future__ import annotations

import hashlib
import logging
import secrets
import sqlite3
from typing import Any

from device_logic.http import now

_log = logging.getLogger(__name__)

# Returned by lookup when DB cannot be queried (import/connection/table error).
DB_UNAVAILABLE: Any = object()


def token_hash(token: str) -> str:
    """SHA-256 hex digest of a raw token (same as stored token_hash)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def lookup_device_id_by_token(token: str) -> str | None | object:
    """Resolve plaintext token → device_id via v2_device_token.

    Returns:
        str — device_id when the token hash matches a row.
        None — DB was reachable but no matching row.
        DB_UNAVAILABLE — DB import/connect/query failed (caller may fall back to env).
    """
    if not token:
        return None
    try:
        from device_logic.db import connect
    except Exception as exc:  # pragma: no cover - import edge
        _log.warning("device_logic.db unavailable for token lookup: %s", exc)
        return DB_UNAVAILABLE
    digest = token_hash(token)
    try:
        with connect() as conn:
            row = conn.execute(
                "SELECT device_id FROM v2_device_token WHERE token_hash=? LIMIT 1",
                (digest,),
            ).fetchone()
        if row is None:
            return None
        return str(row["device_id"] if not isinstance(row, tuple) else row[0])
    except Exception as exc:
        _log.warning("DB token lookup failed (%s); env fallback may apply", exc)
        return DB_UNAVAILABLE


def ensure_device_token(conn: sqlite3.Connection, device_id: str) -> tuple[str | None, bool]:
    """Create a DLC API token on first bind; never rotate on re-bind.

    Returns:
        (plaintext_token, issued_now) — plaintext is only set when newly issued.
    """
    row = conn.execute(
        "SELECT device_id FROM v2_device_token WHERE device_id=? LIMIT 1",
        (device_id,),
    ).fetchone()
    if row is not None:
        return None, False

    token = secrets.token_urlsafe(32)
    ts = now()
    conn.execute(
        """
        INSERT INTO v2_device_token (device_id, token_hash, created_at, rotated_at)
        VALUES (?, ?, ?, ?)
        """,
        (device_id, token_hash(token), ts, ts),
    )
    return token, True


def rotate_device_token(conn: sqlite3.Connection, device_id: str) -> str:
    """Replace the device DLC API token and return the new plaintext once."""
    token = secrets.token_urlsafe(32)
    ts = now()
    conn.execute(
        """
        INSERT INTO v2_device_token (device_id, token_hash, created_at, rotated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(device_id) DO UPDATE SET
            token_hash=excluded.token_hash,
            rotated_at=excluded.rotated_at
        """,
        (device_id, token_hash(token), ts, ts),
    )
    return token
