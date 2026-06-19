"""Default value tests."""

from tests.xiaozhi_schema.conftest import _insert_device


def test_account_default_role_and_status(db):
    db.execute("INSERT INTO v2_account (id, phone) VALUES ('a-1', '+86-1')")
    row = db.execute("SELECT * FROM v2_account WHERE id='a-1'").fetchone()
    assert row["role"] == "user"
    assert row["status"] == "active"


def test_device_default_status(db):
    db.execute("INSERT INTO v2_device (id, device_sn, model) VALUES ('d-1', 'SN-001', 'esp32s3_xyz')")
    row = db.execute("SELECT * FROM v2_device WHERE id='d-1'").fetchone()
    assert row["status"] == "offline"


def test_task_default_status_and_source(db):
    _insert_device(db, "d-1")
    db.execute("INSERT INTO v2_task (id, device_id, intent) VALUES ('t-1', 'd-1', 'calibrate')")
    row = db.execute("SELECT * FROM v2_task WHERE id='t-1'").fetchone()
    assert row["status"] == "pending"
    assert row["source"] == "api"
    assert row["progress"] == 0.0


def test_supply_default_level_and_status(db):
    _insert_device(db, "d-1")
    db.execute("INSERT INTO v2_device_supply (id, device_id, supply_type) VALUES ('s-1', 'd-1', 'battery')")
    row = db.execute("SELECT * FROM v2_device_supply WHERE id='s-1'").fetchone()
    assert row["level"] == 1.0
    assert row["status"] == "normal"


def test_selfcheck_default_result_and_triggered_by(db):
    _insert_device(db, "d-1")
    db.execute("INSERT INTO v2_self_check_event (id, device_id, check_type) VALUES ('sc-1', 'd-1', 'periodic')")
    row = db.execute("SELECT * FROM v2_self_check_event WHERE id='sc-1'").fetchone()
    assert row["result"] == "pass"
    assert row["triggered_by"] == "system"
