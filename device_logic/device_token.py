"""Per-device DLC API token issuance (v2_device_token)."""

from __future__ import annotations

import hashlib
import secrets
import sqlite3

from device_logic.http import now


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


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
        (device_id, _token_hash(token), ts, ts),
    )
    return token, True
