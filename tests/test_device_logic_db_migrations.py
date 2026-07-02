"""Self-check for db_migrations: idempotency and column-add gating."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from device_logic.db_migrations import apply_migrations


def _base_schema(conn: sqlite3.Connection) -> None:
    """Create the prerequisite tables that migrations expect to pre-exist."""
    conn.executescript(
        """
        CREATE TABLE v2_account (
            id TEXT PRIMARY KEY,
            phone TEXT,
            nickname TEXT
        );
        CREATE TABLE v2_voiceprint (
            id TEXT PRIMARY KEY,
            account_id TEXT,
            device_id TEXT
        );
        CREATE TABLE v2_device (
            id TEXT PRIMARY KEY,
            device_sn TEXT
        );
        """
    )
    conn.commit()


def test_apply_migrations_is_idempotent(tmp_path: Path) -> None:
    """Running apply_migrations twice must not raise (IF NOT EXISTS + column guards)."""
    db_file = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_file))
    _base_schema(conn)
    apply_migrations(conn)
    apply_migrations(conn)  # second run must be a no-op
    # Verify a migrated table exists
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "v2_captcha" in tables
    assert "v2_api_key" in tables
    # Verify column add happened
    cols = {row[1] for row in conn.execute("PRAGMA table_info(v2_account)")}
    assert "password_hash" in cols
    assert "email" in cols
    conn.close()


def test_apply_migrations_creates_all_expected_tables(tmp_path: Path) -> None:
    """All 11 v2_* tables from the DDL list must appear after migration."""
    db_file = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_file))
    _base_schema(conn)
    apply_migrations(conn)
    expected = {
        "v2_captcha",
        "v2_pair_request",
        "v2_chat_session",
        "v2_chat_message",
        "v2_audio_record",
        "v2_task_template",
        "v2_notification_subscription",
        "v2_notification_log",
        "v2_device_share",
        "v2_asset_library",
        "v2_api_key",
    }
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    missing = expected - tables
    assert not missing, f"missing tables: {missing}"
    conn.close()


def test_apply_migrations_email_unique_index(tmp_path: Path) -> None:
    """The post-column-add unique index on v2_account(email) must exist."""
    db_file = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_file))
    _base_schema(conn)
    apply_migrations(conn)
    indexes = {row[1] for row in conn.execute("PRAGMA index_list(v2_account)")}
    assert "idx_v2_account_email" in indexes
    conn.close()
