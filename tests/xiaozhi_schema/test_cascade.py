"""Delete/cascade behavior tests."""

import sqlite3

import pytest

from tests.xiaozhi_schema.conftest import _insert_account, _insert_device


def test_cannot_delete_referenced_device(db):
    """Deleting a device still referenced by a binding should fail."""
    _insert_account(db, "a-1")
    _insert_device(db, "d-1")
    db.execute("INSERT INTO v2_device_binding (id, device_id, account_id) VALUES ('b-1', 'd-1', 'a-1')")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("DELETE FROM v2_device WHERE id='d-1'")


def test_cannot_delete_referenced_account(db):
    """Deleting an account still referenced by a binding should fail."""
    _insert_account(db, "a-1")
    _insert_device(db, "d-1")
    db.execute("INSERT INTO v2_device_binding (id, device_id, account_id) VALUES ('b-1', 'd-1', 'a-1')")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("DELETE FROM v2_account WHERE id='a-1'")


def test_delete_orphaned_device_succeeds(db):
    """A device with no references can be deleted."""
    _insert_device(db, "d-1")
    db.execute("DELETE FROM v2_device WHERE id='d-1'")
    row = db.execute("SELECT * FROM v2_device WHERE id='d-1'").fetchone()
    assert row is None
