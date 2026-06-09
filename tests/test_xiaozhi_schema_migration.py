"""Tests for migrations/xiaozhi_schema.sql.

Applies the schema to an in-memory SQLite database and verifies
all 10 tables, constraints, foreign keys, triggers, and indices.
"""
import sqlite3
import pathlib
import time

import pytest


# -- helpers -----------------------------------------------------------

SCHEMA_PATH = (
    pathlib.Path(__file__).resolve().parent.parent
    / "migrations" / "xiaozhi_schema.sql"
)

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
    rows = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    return [r["name"] for r in rows]


def _insert_account(db: sqlite3.Connection, id_: str = "a-1", **kw) -> str:
    phone = kw.pop("phone", f"+86-{id_}")
    db.execute(
        "INSERT INTO v2_account (id, phone) VALUES (?, ?)", (id_, phone)
    )
    return id_


def _insert_device(db: sqlite3.Connection, id_: str = "d-1", sn: str = "SN-001", **kw) -> str:
    db.execute(
        "INSERT INTO v2_device (id, device_sn, model) VALUES (?, ?, ?)",
        (id_, sn, kw.pop("model", "esp32s3_xyz")),
    )
    return id_


# -- table existence ---------------------------------------------------

def test_all_10_tables_exist(db):
    names = _table_names(db)
    for t in ALL_TABLES:
        assert t in names, f"table {t} missing from schema"
    assert len([n for n in names if n in ALL_TABLES]) == 10


# -- foreign key constraints -------------------------------------------

def test_fk_device_binding_enforced(db):
    """Binding with non-existent device_id should fail."""
    _insert_account(db, "a-1")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO v2_device_binding (id, device_id, account_id) "
            "VALUES ('b-1', 'nonexistent', 'a-1')"
        )


def test_fk_device_binding_account_enforced(db):
    """Binding with non-existent account_id should fail."""
    _insert_device(db, "d-1")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO v2_device_binding (id, device_id, account_id) "
            "VALUES ('b-1', 'd-1', 'nonexistent')"
        )


def test_fk_binding_valid_insert_succeeds(db):
    _insert_account(db, "a-1")
    _insert_device(db, "d-1")
    db.execute(
        "INSERT INTO v2_device_binding (id, device_id, account_id) "
        "VALUES ('b-1', 'd-1', 'a-1')"
    )
    row = db.execute("SELECT * FROM v2_device_binding WHERE id='b-1'").fetchone()
    assert row["device_id"] == "d-1"
    assert row["account_id"] == "a-1"


def test_fk_task_device_enforced(db):
    """Task with non-existent device should fail."""
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO v2_task (id, device_id, intent) "
            "VALUES ('t-1', 'nonexistent', 'draw_image')"
        )


def test_fk_member_enforced(db):
    """Member with non-existent account should fail."""
    _insert_device(db, "d-1")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO v2_member (id, account_id, device_id, name) "
            "VALUES ('m-1', 'nonexistent', 'd-1', 'test')"
        )


def test_fk_rma_device_enforced(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO v2_device_rma_event (id, device_id, reason) "
            "VALUES ('r-1', 'nonexistent', 'test')"
        )


def test_fk_supply_device_enforced(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO v2_device_supply (id, device_id, supply_type) "
            "VALUES ('s-1', 'nonexistent', 'pen')"
        )


# -- CHECK constraints -------------------------------------------------

def test_account_role_check_enforced(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO v2_account (id, phone, role) "
            "VALUES ('a-1', '+86-1', 'superadmin')"
        )


def test_account_status_check_enforced(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO v2_account (id, phone, status) "
            "VALUES ('a-1', '+86-2', 'banned')"
        )


def test_device_status_check_enforced(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO v2_device (id, device_sn, model, status) "
            "VALUES ('d-1', 'SN-001', 'esp32s3_xyz', 'broken')"
        )


def test_binding_mode_check_enforced(db):
    _insert_account(db, "a-1")
    _insert_device(db, "d-1")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO v2_device_binding (id, device_id, account_id, bind_mode) "
            "VALUES ('b-1', 'd-1', 'a-1', 'admin')"
        )


def test_task_status_check_enforced(db):
    _insert_device(db, "d-1")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO v2_task (id, device_id, intent, status) "
            "VALUES ('t-1', 'd-1', 'draw_image', 'unknown')"
        )


def test_task_source_check_enforced(db):
    _insert_device(db, "d-1")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO v2_task (id, device_id, intent, source) "
            "VALUES ('t-1', 'd-1', 'draw_image', 'cli')"
        )


def test_member_role_check_enforced(db):
    _insert_account(db, "a-1")
    _insert_device(db, "d-1")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO v2_member (id, account_id, device_id, name, role) "
            "VALUES ('m-1', 'a-1', 'd-1', 'test', 'robot')"
        )


def test_voiceprint_status_check_enforced(db):
    _insert_account(db, "a-1")
    _insert_device(db, "d-1")
    _insert_device(db, "d-2", sn="SN-002")
    # Need a member first because voiceprint references member
    db.execute(
        "INSERT INTO v2_member (id, account_id, device_id, name) "
        "VALUES ('m-1', 'a-1', 'd-1', 'test')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO v2_voiceprint (id, member_id, device_id, status) "
            "VALUES ('v-1', 'm-1', 'd-2', 'unknown')"
        )


def test_rma_type_check_enforced(db):
    _insert_device(db, "d-1")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO v2_device_rma_event (id, device_id, rma_type) "
            "VALUES ('r-1', 'd-1', 'refund')"
        )


def test_rma_status_check_enforced(db):
    _insert_device(db, "d-1")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO v2_device_rma_event (id, device_id, status) "
            "VALUES ('r-1', 'd-1', 'unknown')"
        )


def test_supply_status_check_enforced(db):
    _insert_device(db, "d-1")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO v2_device_supply (id, device_id, supply_type, status) "
            "VALUES ('s-1', 'd-1', 'pen', 'critical')"
        )


def test_selfcheck_result_check_enforced(db):
    _insert_device(db, "d-1")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO v2_self_check_event (id, device_id, check_type, result) "
            "VALUES ('sc-1', 'd-1', 'startup', 'error')"
        )


def test_selfcheck_triggered_by_check_enforced(db):
    _insert_device(db, "d-1")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO v2_self_check_event (id, device_id, check_type, triggered_by) "
            "VALUES ('sc-1', 'd-1', 'startup', 'cron')"
        )


# -- UNIQUE constraints -------------------------------------------------

def test_account_phone_unique(db):
    db.execute("INSERT INTO v2_account (id, phone) VALUES ('a-1', '+86-1')")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO v2_account (id, phone) VALUES ('a-2', '+86-1')")


def test_device_sn_unique(db):
    db.execute(
        "INSERT INTO v2_device (id, device_sn, model) "
        "VALUES ('d-1', 'SN-001', 'esp32s3_xyz')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO v2_device (id, device_sn, model) "
            "VALUES ('d-2', 'SN-001', 'esp32c3_mini')"
        )


def test_binding_unique(db):
    _insert_account(db, "a-1")
    _insert_device(db, "d-1")
    db.execute(
        "INSERT INTO v2_device_binding (id, device_id, account_id) "
        "VALUES ('b-1', 'd-1', 'a-1')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO v2_device_binding (id, device_id, account_id) "
            "VALUES ('b-2', 'd-1', 'a-1')"
        )


def test_supply_unique_per_device(db):
    _insert_device(db, "d-1")
    db.execute(
        "INSERT INTO v2_device_supply (id, device_id, supply_type) "
        "VALUES ('s-1', 'd-1', 'pen')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO v2_device_supply (id, device_id, supply_type) "
            "VALUES ('s-2', 'd-1', 'pen')"
        )
    # Different supply_type on the same device should work
    db.execute(
        "INSERT INTO v2_device_supply (id, device_id, supply_type) "
        "VALUES ('s-3', 'd-1', 'paper')"
    )


# -- NOT NULL constraints -----------------------------------------------

def test_device_sn_not_null(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO v2_device (id, model) VALUES ('d-1', 'esp32s3_xyz')"
        )


def test_device_model_not_null(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO v2_device (id, device_sn) VALUES ('d-1', 'SN-001')"
        )


def test_member_name_not_null(db):
    _insert_account(db, "a-1")
    _insert_device(db, "d-1")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO v2_member (id, account_id, device_id) "
            "VALUES ('m-1', 'a-1', 'd-1')"
        )


def test_task_intent_not_null(db):
    _insert_device(db, "d-1")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO v2_task (id, device_id) VALUES ('t-1', 'd-1')"
        )


def test_supply_type_not_null(db):
    _insert_device(db, "d-1")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO v2_device_supply (id, device_id) "
            "VALUES ('s-1', 'd-1')"
        )


def test_selfcheck_type_not_null(db):
    _insert_device(db, "d-1")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO v2_self_check_event (id, device_id) "
            "VALUES ('sc-1', 'd-1')"
        )


# -- updated_at trigger tests -------------------------------------------

def test_account_updated_at_trigger(db):
    db.execute("INSERT INTO v2_account (id, phone) VALUES ('a-1', '+86-1')")
    before = db.execute(
        "SELECT updated_at FROM v2_account WHERE id='a-1'"
    ).fetchone()["updated_at"]
    assert before is not None
    time.sleep(1.1)  # SQLite datetime('now') has second resolution
    db.execute("UPDATE v2_account SET nickname='neo' WHERE id='a-1'")
    after = db.execute(
        "SELECT updated_at FROM v2_account WHERE id='a-1'"
    ).fetchone()["updated_at"]
    assert after != before


def test_device_updated_at_trigger(db):
    db.execute(
        "INSERT INTO v2_device (id, device_sn, model) "
        "VALUES ('d-1', 'SN-001', 'esp32s3_xyz')"
    )
    before = db.execute(
        "SELECT updated_at FROM v2_device WHERE id='d-1'"
    ).fetchone()["updated_at"]
    time.sleep(1.1)
    db.execute("UPDATE v2_device SET firmware_ver='2.0' WHERE id='d-1'")
    after = db.execute(
        "SELECT updated_at FROM v2_device WHERE id='d-1'"
    ).fetchone()["updated_at"]
    assert after != before


def test_member_updated_at_trigger(db):
    _insert_account(db, "a-1")
    _insert_device(db, "d-1")
    db.execute(
        "INSERT INTO v2_member (id, account_id, device_id, name) "
        "VALUES ('m-1', 'a-1', 'd-1', 'child1')"
    )
    before = db.execute(
        "SELECT updated_at FROM v2_member WHERE id='m-1'"
    ).fetchone()["updated_at"]
    time.sleep(1.1)
    db.execute("UPDATE v2_member SET role='parent' WHERE id='m-1'")
    after = db.execute(
        "SELECT updated_at FROM v2_member WHERE id='m-1'"
    ).fetchone()["updated_at"]
    assert after != before


def test_task_updated_at_trigger(db):
    _insert_device(db, "d-1")
    db.execute(
        "INSERT INTO v2_task (id, device_id, intent) "
        "VALUES ('t-1', 'd-1', 'draw_image')"
    )
    before = db.execute(
        "SELECT updated_at FROM v2_task WHERE id='t-1'"
    ).fetchone()["updated_at"]
    time.sleep(1.1)
    db.execute("UPDATE v2_task SET status='running' WHERE id='t-1'")
    after = db.execute(
        "SELECT updated_at FROM v2_task WHERE id='t-1'"
    ).fetchone()["updated_at"]
    assert after != before


def test_voiceprint_updated_at_trigger(db):
    _insert_account(db, "a-1")
    _insert_device(db, "d-1")
    db.execute(
        "INSERT INTO v2_member (id, account_id, device_id, name) "
        "VALUES ('m-1', 'a-1', 'd-1', 'child1')"
    )
    db.execute(
        "INSERT INTO v2_voiceprint (id, member_id, device_id) "
        "VALUES ('v-1', 'm-1', 'd-1')"
    )
    before = db.execute(
        "SELECT updated_at FROM v2_voiceprint WHERE id='v-1'"
    ).fetchone()["updated_at"]
    time.sleep(1.1)
    db.execute(
        "UPDATE v2_voiceprint SET sample_count=5 WHERE id='v-1'"
    )
    after = db.execute(
        "SELECT updated_at FROM v2_voiceprint WHERE id='v-1'"
    ).fetchone()["updated_at"]
    assert after != before


def test_transfer_updated_at_trigger(db):
    _insert_account(db, "a-1")
    _insert_account(db, "a-2", phone="+86-2")
    _insert_device(db, "d-1")
    db.execute(
        "INSERT INTO v2_device_transfer_request "
        "(id, device_id, from_account_id, to_account_id) "
        "VALUES ('tfr-1', 'd-1', 'a-1', 'a-2')"
    )
    before = db.execute(
        "SELECT updated_at FROM v2_device_transfer_request WHERE id='tfr-1'"
    ).fetchone()["updated_at"]
    time.sleep(1.1)
    db.execute(
        "UPDATE v2_device_transfer_request SET status='accepted' WHERE id='tfr-1'"
    )
    after = db.execute(
        "SELECT updated_at FROM v2_device_transfer_request WHERE id='tfr-1'"
    ).fetchone()["updated_at"]
    assert after != before


def test_rma_updated_at_trigger(db):
    _insert_device(db, "d-1")
    db.execute(
        "INSERT INTO v2_device_rma_event (id, device_id, reason) "
        "VALUES ('r-1', 'd-1', 'motor failure')"
    )
    before = db.execute(
        "SELECT updated_at FROM v2_device_rma_event WHERE id='r-1'"
    ).fetchone()["updated_at"]
    time.sleep(1.1)
    db.execute(
        "UPDATE v2_device_rma_event SET status='in_progress' WHERE id='r-1'"
    )
    after = db.execute(
        "SELECT updated_at FROM v2_device_rma_event WHERE id='r-1'"
    ).fetchone()["updated_at"]
    assert after != before


def test_supply_updated_at_trigger(db):
    _insert_device(db, "d-1")
    db.execute(
        "INSERT INTO v2_device_supply (id, device_id, supply_type) "
        "VALUES ('s-1', 'd-1', 'pen')"
    )
    before = db.execute(
        "SELECT updated_at FROM v2_device_supply WHERE id='s-1'"
    ).fetchone()["updated_at"]
    time.sleep(1.1)
    db.execute(
        "UPDATE v2_device_supply SET level=0.5 WHERE id='s-1'"
    )
    after = db.execute(
        "SELECT updated_at FROM v2_device_supply WHERE id='s-1'"
    ).fetchone()["updated_at"]
    assert after != before


# -- default values -----------------------------------------------------

def test_account_default_role_and_status(db):
    db.execute("INSERT INTO v2_account (id, phone) VALUES ('a-1', '+86-1')")
    row = db.execute("SELECT * FROM v2_account WHERE id='a-1'").fetchone()
    assert row["role"] == "user"
    assert row["status"] == "active"


def test_device_default_status(db):
    db.execute(
        "INSERT INTO v2_device (id, device_sn, model) "
        "VALUES ('d-1', 'SN-001', 'esp32s3_xyz')"
    )
    row = db.execute("SELECT * FROM v2_device WHERE id='d-1'").fetchone()
    assert row["status"] == "offline"


def test_task_default_status_and_source(db):
    _insert_device(db, "d-1")
    db.execute(
        "INSERT INTO v2_task (id, device_id, intent) "
        "VALUES ('t-1', 'd-1', 'calibrate')"
    )
    row = db.execute("SELECT * FROM v2_task WHERE id='t-1'").fetchone()
    assert row["status"] == "pending"
    assert row["source"] == "api"
    assert row["progress"] == 0.0


def test_supply_default_level_and_status(db):
    _insert_device(db, "d-1")
    db.execute(
        "INSERT INTO v2_device_supply (id, device_id, supply_type) "
        "VALUES ('s-1', 'd-1', 'battery')"
    )
    row = db.execute(
        "SELECT * FROM v2_device_supply WHERE id='s-1'"
    ).fetchone()
    assert row["level"] == 1.0
    assert row["status"] == "normal"


def test_selfcheck_default_result_and_triggered_by(db):
    _insert_device(db, "d-1")
    db.execute(
        "INSERT INTO v2_self_check_event (id, device_id, check_type) "
        "VALUES ('sc-1', 'd-1', 'periodic')"
    )
    row = db.execute(
        "SELECT * FROM v2_self_check_event WHERE id='sc-1'"
    ).fetchone()
    assert row["result"] == "pass"
    assert row["triggered_by"] == "system"


# -- indices ------------------------------------------------------------

def test_indices_exist(db):
    """Verify key indices are present."""
    indices = {
        row["name"]
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()
    }
    expected = {
        "idx_v2_account_phone",
        "idx_v2_account_wechat",
        "idx_v2_device_sn",
        "idx_v2_device_status",
        "idx_v2_binding_device",
        "idx_v2_binding_account",
        "idx_v2_member_device",
        "idx_v2_member_account",
        "idx_v2_voiceprint_member",
        "idx_v2_voiceprint_device",
        "idx_v2_task_device",
        "idx_v2_task_status",
        "idx_v2_task_created",
        "idx_v2_transfer_device",
        "idx_v2_transfer_to",
        "idx_v2_transfer_status",
        "idx_v2_rma_device",
        "idx_v2_rma_status",
        "idx_v2_supply_device",
        "idx_v2_selfcheck_device",
        "idx_v2_selfcheck_result",
        "idx_v2_selfcheck_created",
    }
    missing = expected - indices
    assert not missing, f"missing indices: {missing}"


# -- cascade / delete behaviour -----------------------------------------

def test_cannot_delete_referenced_device(db):
    """Deleting a device still referenced by a binding should fail."""
    _insert_account(db, "a-1")
    _insert_device(db, "d-1")
    db.execute(
        "INSERT INTO v2_device_binding (id, device_id, account_id) "
        "VALUES ('b-1', 'd-1', 'a-1')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("DELETE FROM v2_device WHERE id='d-1'")


def test_cannot_delete_referenced_account(db):
    """Deleting an account still referenced by a binding should fail."""
    _insert_account(db, "a-1")
    _insert_device(db, "d-1")
    db.execute(
        "INSERT INTO v2_device_binding (id, device_id, account_id) "
        "VALUES ('b-1', 'd-1', 'a-1')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("DELETE FROM v2_account WHERE id='a-1'")


def test_delete_orphaned_device_succeeds(db):
    """A device with no references can be deleted."""
    _insert_device(db, "d-1")
    db.execute("DELETE FROM v2_device WHERE id='d-1'")
    row = db.execute(
        "SELECT * FROM v2_device WHERE id='d-1'"
    ).fetchone()
    assert row is None
