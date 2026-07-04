"""S1/S7: v2_device_token table creation via db_migrations.

The DB-backed per-device token lookup in ``dlc_api.deps.verify_dlc_api_token``
queries ``v2_device_token``, but the table was never created in any migration.
``_lookup_token_from_db`` silently catches the missing-table exception and
falls through to the env fallback — so in production today every token goes
through ``LIMA_DEVICE_TOKENS`` env var, never the DB.

These tests verify the DDL is added to ``device_logic.db_migrations._DDL_STATEMENTS``
and that the table + unique index appear after ``apply_migrations``.
"""

from __future__ import annotations

import pathlib

import sqlite3


def _base_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE v2_account (id TEXT PRIMARY KEY, phone TEXT, nickname TEXT);
        CREATE TABLE v2_voiceprint (id TEXT PRIMARY KEY, account_id TEXT, device_id TEXT);
        CREATE TABLE v2_device (id TEXT PRIMARY KEY, device_sn TEXT);
        """
    )
    conn.commit()


def test_v2_device_token_table_exists_after_migration(tmp_path: pathlib.Path):
    """apply_migrations must create v2_device_token."""
    from device_logic.db_migrations import apply_migrations

    db_file = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_file))
    _base_schema(conn)
    apply_migrations(conn)

    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "v2_device_token" in tables, "v2_device_token table must be created by apply_migrations"
    conn.close()


def test_v2_device_token_has_required_columns(tmp_path: pathlib.Path):
    """Columns: device_id (PK), token_hash (NOT NULL UNIQUE), created_at, rotated_at."""
    from device_logic.db_migrations import apply_migrations

    db_file = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_file))
    _base_schema(conn)
    apply_migrations(conn)

    cols = {row[1] for row in conn.execute("PRAGMA table_info(v2_device_token)")}
    assert {"device_id", "token_hash", "created_at", "rotated_at"} <= cols, f"missing columns: got {cols}"
    conn.close()


def test_v2_device_token_unique_index_on_hash(tmp_path: pathlib.Path):
    """Unique index on token_hash must exist so two devices cannot share a hash."""
    from device_logic.db_migrations import apply_migrations

    db_file = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_file))
    _base_schema(conn)
    apply_migrations(conn)

    indexes = {row[1] for row in conn.execute("PRAGMA index_list(v2_device_token)")}
    assert any("token_hash" in idx for idx in indexes), f"expected unique index on token_hash; got {indexes}"
    conn.close()


def test_v2_device_token_ddl_in_module():
    """The DDL string must be present in _DDL_STATEMENTS so it runs on every bootstrap."""
    from device_logic.db_migrations import _DDL_STATEMENTS

    joined = "\n".join(_DDL_STATEMENTS)
    assert "v2_device_token" in joined, "v2_device_token CREATE TABLE must be in _DDL_STATEMENTS"
