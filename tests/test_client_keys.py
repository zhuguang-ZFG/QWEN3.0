"""Tests for client_keys: no plaintext persistence, hash-based quota, legacy migration."""

from __future__ import annotations

import sqlite3
import time

import pytest

from client_keys.quota import QuotaTracker
from client_keys.storage import ClientKeyStorage, _hash_token


@pytest.fixture
def store(tmp_path) -> ClientKeyStorage:
    return ClientKeyStorage(str(tmp_path / "keys.db"))


def _columns(db_path: str) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        return {row[1] for row in conn.execute("PRAGMA table_info(client_keys)")}


def test_create_returns_plaintext_but_db_stores_only_hash(store, tmp_path):
    key = store.create("alpha")
    assert key.key_value and key.key_value.startswith("lima-")
    assert key.key_hash == _hash_token(key.key_value)

    db_path = str(tmp_path / "keys.db")
    assert "key_value" not in _columns(db_path)
    with sqlite3.connect(db_path) as conn:
        blob = conn.execute("SELECT * FROM client_keys").fetchone()
    assert key.key_value not in map(str, blob)
    assert key.key_hash in blob


def test_get_by_value_hits_via_hash_and_hides_plaintext(store):
    created = store.create("beta")
    fetched = store.get_by_value(created.key_value)
    assert fetched is not None
    assert fetched.key_id == created.key_id
    assert fetched.key_hash == created.key_hash
    assert fetched.key_value is None
    assert store.get_by_value("lima-not-a-real-key") is None


def test_list_and_get_by_key_id_expose_no_plaintext(store):
    created = store.create("gamma")
    listed = store.list_all()
    assert len(listed) == 1
    assert listed[0].key_value is None
    by_id = store.get_by_key_id(created.key_id)
    assert by_id is not None
    assert by_id.key_value is None


def test_regenerate_reveals_new_value_once(store):
    created = store.create("delta")
    regenerated = store.regenerate(created.key_id)
    assert regenerated is not None
    assert regenerated.key_value is not None
    assert regenerated.key_value != created.key_value
    assert regenerated.key_hash == _hash_token(regenerated.key_value)
    # Old plaintext no longer resolves; new one does and carries no plaintext.
    assert store.get_by_value(created.key_value) is None
    fetched = store.get_by_value(regenerated.key_value)
    assert fetched is not None
    assert fetched.key_value is None
    assert store.regenerate("ck-missing") is None


def test_quota_works_from_hash_only(store, tmp_path):
    db_path = str(tmp_path / "keys.db")
    created = store.create("epsilon", quota_daily=2)
    tracker = QuotaTracker(db_path)
    # Simulate a key loaded from storage: plaintext is gone.
    key = store.get_by_key_id(created.key_id)
    assert key.key_value is None

    assert tracker.try_consume_quota(key) == (True, "")
    assert tracker.check_key_quota(key) is True
    assert tracker.try_consume_quota(key) == (True, "")
    allowed, reason = tracker.try_consume_quota(key)
    assert (allowed, reason) == (False, "daily_limit")

    summary = tracker.usage_summary(key.key_hash)
    assert summary["daily_count"] == 2

    tracker.clear_token(key.key_hash)
    assert tracker.usage_summary(key.key_hash)["daily_count"] == 0


def test_legacy_plaintext_schema_is_migrated(tmp_path):
    db_path = str(tmp_path / "legacy.db")
    plaintext = "lima-deadbeef-cafebabe-0123456789abcdef"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE client_keys (
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
            "INSERT INTO client_keys (key_id, key_hash, key_value, label, created_at) VALUES (?, ?, ?, ?, ?)",
            ("ck-legacy", "stale-hash", plaintext, "legacy", time.time()),
        )
        conn.commit()

    store = ClientKeyStorage(db_path)
    assert "key_value" not in _columns(db_path)
    migrated = store.get_by_value(plaintext)
    assert migrated is not None
    assert migrated.key_id == "ck-legacy"
    assert migrated.key_hash == _hash_token(plaintext)
    assert migrated.key_value is None
