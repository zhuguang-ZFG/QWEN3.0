"""Foreign-key constraint tests."""

import sqlite3

import pytest

from tests.xiaozhi_schema.conftest import _insert_account, _insert_device


def test_fk_device_binding_enforced(db):
    """Binding with non-existent device_id should fail."""
    _insert_account(db, "a-1")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO v2_device_binding (id, device_id, account_id) VALUES ('b-1', 'nonexistent', 'a-1')")


def test_fk_device_binding_account_enforced(db):
    """Binding with non-existent account_id should fail."""
    _insert_device(db, "d-1")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO v2_device_binding (id, device_id, account_id) VALUES ('b-1', 'd-1', 'nonexistent')")


def test_fk_binding_valid_insert_succeeds(db):
    _insert_account(db, "a-1")
    _insert_device(db, "d-1")
    db.execute("INSERT INTO v2_device_binding (id, device_id, account_id) VALUES ('b-1', 'd-1', 'a-1')")
    row = db.execute("SELECT * FROM v2_device_binding WHERE id='b-1'").fetchone()
    assert row["device_id"] == "d-1"
    assert row["account_id"] == "a-1"


def test_fk_task_device_enforced(db):
    """Task with non-existent device should fail."""
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO v2_task (id, device_id, intent) VALUES ('t-1', 'nonexistent', 'draw_image')")


def test_fk_member_enforced(db):
    """Member with non-existent account should fail."""
    _insert_device(db, "d-1")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO v2_member (id, account_id, device_id, name) VALUES ('m-1', 'nonexistent', 'd-1', 'test')"
        )


def test_fk_rma_device_enforced(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO v2_device_rma_event (id, device_id, reason) VALUES ('r-1', 'nonexistent', 'test')")


def test_fk_supply_device_enforced(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO v2_device_supply (id, device_id, supply_type) VALUES ('s-1', 'nonexistent', 'pen')")
