"""Shared fixtures and helpers for xiaozhi schema tests."""

import pathlib
import sqlite3

import pytest


SCHEMA_PATH = pathlib.Path(__file__).resolve().parent.parent.parent / "migrations" / "xiaozhi_schema.sql"

ALL_TABLES = [
    "v2_account",
    "v2_device",
    "v2_device_binding",
    "v2_member",
    "v2_voiceprint",
    "v2_task",
    "v2_device_transfer_request",
    "v2_device_rma_event",
    "v2_device_supply",
    "v2_self_check_event",
]

TABLES_WITH_UPDATED_AT = [
    "v2_account",
    "v2_device",
    "v2_member",
    "v2_task",
    "v2_voiceprint",
    "v2_device_transfer_request",
    "v2_device_rma_event",
    "v2_device_supply",
]


def _schema_sql() -> str:
    return SCHEMA_PATH.read_text(encoding="utf-8")


@pytest.fixture
def db():
    """Return a fresh in-memory SQLite database with the full schema applied."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_schema_sql())
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


def _table_names(db: sqlite3.Connection) -> list[str]:
    rows = db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    return [r["name"] for r in rows]


def _insert_account(db: sqlite3.Connection, id_: str = "a-1", **kw) -> str:
    phone = kw.pop("phone", f"+86-{id_}")
    db.execute("INSERT INTO v2_account (id, phone) VALUES (?, ?)", (id_, phone))
    return id_


def _insert_device(db: sqlite3.Connection, id_: str = "d-1", sn: str = "SN-001", **kw) -> str:
    db.execute(
        "INSERT INTO v2_device (id, device_sn, model) VALUES (?, ?, ?)",
        (id_, sn, kw.pop("model", "esp32s3_xyz")),
    )
    return id_
