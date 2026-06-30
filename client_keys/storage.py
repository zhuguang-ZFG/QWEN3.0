"""SQLite-backed storage for client API keys."""

from __future__ import annotations

import hashlib
import logging
import secrets
import sqlite3
import threading
import time
from pathlib import Path

from client_keys.models import ClientKey

_log = logging.getLogger(__name__)

_KEY_PREFIX = "lima-"
_KEY_ID_PREFIX = "ck-"


class ClientKeyStorageError(RuntimeError):
    """Raised when the client key store cannot be read or written."""


class ClientKeyStorage:
    """Persistent store for client API keys using SQLite."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._ensure_schema()

    def _connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=10.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        try:
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
            with self._connection() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS client_keys (
                        key_id TEXT PRIMARY KEY,
                        key_hash TEXT UNIQUE NOT NULL,
                        key_value TEXT NOT NULL,
                        label TEXT NOT NULL,
                        enabled INTEGER NOT NULL DEFAULT 1,
                        created_at REAL NOT NULL,
                        quota_daily INTEGER NOT NULL DEFAULT 1000,
                        quota_monthly INTEGER NOT NULL DEFAULT 30000,
                        rate_limit_rpm INTEGER NOT NULL DEFAULT 20,
                        allowed_urls TEXT NOT NULL DEFAULT '["*"]',
                        request_count INTEGER NOT NULL DEFAULT 0,
                        last_used_at REAL
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_client_keys_hash ON client_keys(key_hash)"
                )
                conn.commit()
        except (sqlite3.Error, OSError) as exc:
            _log.error("client_keys: failed to initialize schema at %s: %s", self._db_path, exc)
            raise ClientKeyStorageError(f"Failed to initialize client key schema: {exc}") from exc

    def create(
        self,
        label: str,
        quota_daily: int = 1000,
        quota_monthly: int = 30000,
        rate_limit_rpm: int = 20,
        allowed_urls: list[str] | None = None,
    ) -> ClientKey:
        """Create a new client key and return it (including the raw value)."""
        allowed_urls = ["*"] if allowed_urls is None else allowed_urls
        key_value = _generate_key_value()
        record = ClientKey(
            key_id=_new_key_id(key_value),
            key_value=key_value,
            label=label,
            enabled=True,
            created_at=time.time(),
            quota_daily=quota_daily,
            quota_monthly=quota_monthly,
            rate_limit_rpm=rate_limit_rpm,
            allowed_urls=allowed_urls,
        )
        try:
            with self._lock, self._connection() as conn:
                conn.execute(
                    """
                    INSERT INTO client_keys
                    (key_id, key_hash, key_value, label, enabled, created_at,
                     quota_daily, quota_monthly, rate_limit_rpm, allowed_urls)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.key_id,
                        _hash_token(key_value),
                        record.key_value,
                        record.label,
                        int(record.enabled),
                        record.created_at,
                        record.quota_daily,
                        record.quota_monthly,
                        record.rate_limit_rpm,
                        _encode_urls(record.allowed_urls),
                    ),
                )
                conn.commit()
        except sqlite3.Error as exc:
            _log.error("client_keys: failed to create key: %s", exc)
            raise ClientKeyStorageError(f"Failed to create client key: {exc}") from exc
        return record

    def list_all(self) -> list[ClientKey]:
        try:
            with self._lock, self._connection() as conn:
                rows = conn.execute("SELECT * FROM client_keys ORDER BY created_at DESC").fetchall()
        except sqlite3.Error as exc:
            _log.error("client_keys: failed to list keys: %s", exc)
            raise ClientKeyStorageError(f"Failed to list client keys: {exc}") from exc
        return [_row_to_key(row) for row in rows]

    def get_by_key_id(self, key_id: str) -> ClientKey | None:
        try:
            with self._lock, self._connection() as conn:
                row = conn.execute("SELECT * FROM client_keys WHERE key_id = ?", (key_id,)).fetchone()
        except sqlite3.Error as exc:
            _log.error("client_keys: failed to get key %s: %s", key_id, exc)
            raise ClientKeyStorageError(f"Failed to read client key: {exc}") from exc
        return _row_to_key(row) if row else None

    def get_by_value(self, key_value: str) -> ClientKey | None:
        try:
            with self._lock, self._connection() as conn:
                row = conn.execute(
                    "SELECT * FROM client_keys WHERE key_hash = ?", (_hash_token(key_value),)
                ).fetchone()
        except sqlite3.Error as exc:
            _log.error("client_keys: failed to look up key by value: %s", exc)
            raise ClientKeyStorageError(f"Failed to look up client key: {exc}") from exc
        return _row_to_key(row) if row else None

    def update(self, key_id: str, fields: dict) -> bool:
        allowed = {"label", "enabled", "quota_daily", "quota_monthly", "rate_limit_rpm", "allowed_urls"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return False
        if "allowed_urls" in updates:
            updates["allowed_urls"] = _encode_urls(updates["allowed_urls"])
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [key_id]
        try:
            with self._lock, self._connection() as conn:
                cursor = conn.execute(
                    f"UPDATE client_keys SET {set_clause} WHERE key_id = ?", values
                )
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as exc:
            _log.error("client_keys: failed to update key %s: %s", key_id, exc)
            raise ClientKeyStorageError(f"Failed to update client key: {exc}") from exc

    def delete(self, key_id: str) -> bool:
        try:
            with self._lock, self._connection() as conn:
                cursor = conn.execute("DELETE FROM client_keys WHERE key_id = ?", (key_id,))
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as exc:
            _log.error("client_keys: failed to delete key %s: %s", key_id, exc)
            raise ClientKeyStorageError(f"Failed to delete client key: {exc}") from exc

    def regenerate(self, key_id: str) -> ClientKey | None:
        key_value = _generate_key_value()
        try:
            with self._lock, self._connection() as conn:
                cursor = conn.execute(
                    """
                    UPDATE client_keys
                    SET key_hash = ?, key_value = ?,
                        request_count = 0, last_used_at = NULL
                    WHERE key_id = ?
                    """,
                    (_hash_token(key_value), key_value, key_id),
                )
                conn.commit()
                if cursor.rowcount == 0:
                    return None
                row = conn.execute("SELECT * FROM client_keys WHERE key_id = ?", (key_id,)).fetchone()
        except sqlite3.Error as exc:
            _log.error("client_keys: failed to regenerate key %s: %s", key_id, exc)
            raise ClientKeyStorageError(f"Failed to regenerate client key: {exc}") from exc
        return _row_to_key(row) if row else None

    def update_usage(self, key_id: str, request_count: int, last_used_at: float) -> None:
        try:
            with self._lock, self._connection() as conn:
                conn.execute(
                    "UPDATE client_keys SET request_count = ?, last_used_at = ? WHERE key_id = ?",
                    (request_count, last_used_at, key_id),
                )
                conn.commit()
        except sqlite3.Error as exc:
            _log.warning("client_keys: failed to persist usage for %s: %s", key_id, exc)


def _generate_key_value() -> str:
    random_part = secrets.token_hex(16)
    return f"{_KEY_PREFIX}{random_part[:8]}-{random_part[8:16]}-{random_part[16:]}"


def _hash_token(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _new_key_id(value: str) -> str:
    return f"{_KEY_ID_PREFIX}{_hash_token(value)[:12]}"


def _mask_key(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 12:
        return value[:5] + "****"
    return value[:10] + "****" + value[-4:]


def _encode_urls(urls: list[str]) -> str:
    import json

    return json.dumps(urls, ensure_ascii=False)


def _decode_urls(raw: str) -> list[str]:
    import json

    try:
        value = json.loads(raw)
        return value if isinstance(value, list) else ["*"]
    except json.JSONDecodeError:
        _log.warning("client_keys: malformed allowed_urls in storage: %s", raw)
        return ["*"]


def _row_to_key(row: sqlite3.Row) -> ClientKey:
    return ClientKey(
        key_id=row["key_id"],
        key_value=row["key_value"],
        label=row["label"],
        enabled=bool(row["enabled"]),
        created_at=row["created_at"],
        quota_daily=row["quota_daily"],
        quota_monthly=row["quota_monthly"],
        rate_limit_rpm=row["rate_limit_rpm"],
        allowed_urls=_decode_urls(row["allowed_urls"]),
    )
