"""Device-app API key generation and storage helpers."""

from __future__ import annotations

import hashlib
import secrets
from typing import Any

from device_logic.db import connect
from device_logic.http import new_id, now

_KEY_PREFIX = "sk-lima-"
_KEY_RANDOM_BYTES = 24
_PREFIX_VISIBLE_CHARS = 10


def _generate_key() -> tuple[str, str, str]:
    """Return (full_key, key_prefix, key_hash)."""
    raw = _KEY_PREFIX + secrets.token_urlsafe(_KEY_RANDOM_BYTES)
    prefix = raw[: len(_KEY_PREFIX) + _PREFIX_VISIBLE_CHARS]
    key_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return raw, prefix, key_hash


def create_key(account_id: str, name: str) -> dict[str, Any]:
    """Create a new API key for the account. Returns the plaintext key exactly once."""
    key_id = new_id()
    full_key, prefix, key_hash = _generate_key()
    created_at = now()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO v2_api_key (id, account_id, name, key_prefix, key_hash, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'active', ?)
            """,
            (key_id, account_id, name, prefix, key_hash, created_at),
        )
        conn.commit()
    return {
        "id": key_id,
        "name": name,
        "prefix": prefix,
        "key": full_key,
        "status": "active",
        "createdAt": created_at,
    }


def list_keys(account_id: str) -> list[dict[str, Any]]:
    """List active API keys for the account (no secrets)."""
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, name, key_prefix, status, created_at, expires_at, daily_limit
            FROM v2_api_key
            WHERE account_id=? AND status='active'
            ORDER BY created_at DESC
            """,
            (account_id,),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "prefix": row["key_prefix"],
            "status": row["status"],
            "createdAt": row["created_at"],
            "expiresAt": row["expires_at"],
            "dailyLimit": row["daily_limit"],
        }
        for row in rows
    ]


def delete_key(account_id: str, key_id: str) -> bool:
    """Soft-delete an API key. Returns True if the key existed and belonged to the account."""
    with connect() as conn:
        cursor = conn.execute(
            "UPDATE v2_api_key SET status='deleted' WHERE id=? AND account_id=? AND status='active'",
            (key_id, account_id),
        )
        conn.commit()
    return cursor.rowcount > 0
