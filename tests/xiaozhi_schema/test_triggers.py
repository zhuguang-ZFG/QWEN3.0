"""updated_at trigger tests."""

import time

from tests.xiaozhi_schema.conftest import _insert_account, _insert_device


def test_account_updated_at_trigger(db):
    db.execute("INSERT INTO v2_account (id, phone) VALUES ('a-1', '+86-1')")
    before = db.execute("SELECT updated_at FROM v2_account WHERE id='a-1'").fetchone()["updated_at"]
    assert before is not None
    time.sleep(1.1)  # SQLite datetime('now') has second resolution
    db.execute("UPDATE v2_account SET nickname='neo' WHERE id='a-1'")
    after = db.execute("SELECT updated_at FROM v2_account WHERE id='a-1'").fetchone()["updated_at"]
    assert after != before


def test_device_updated_at_trigger(db):
    db.execute("INSERT INTO v2_device (id, device_sn, model) VALUES ('d-1', 'SN-001', 'esp32s3_xyz')")
    before = db.execute("SELECT updated_at FROM v2_device WHERE id='d-1'").fetchone()["updated_at"]
    time.sleep(1.1)
    db.execute("UPDATE v2_device SET firmware_ver='2.0' WHERE id='d-1'")
    after = db.execute("SELECT updated_at FROM v2_device WHERE id='d-1'").fetchone()["updated_at"]
    assert after != before


def test_member_updated_at_trigger(db):
    _insert_account(db, "a-1")
    _insert_device(db, "d-1")
    db.execute("INSERT INTO v2_member (id, account_id, device_id, name) VALUES ('m-1', 'a-1', 'd-1', 'child1')")
    before = db.execute("SELECT updated_at FROM v2_member WHERE id='m-1'").fetchone()["updated_at"]
    time.sleep(1.1)
    db.execute("UPDATE v2_member SET role='parent' WHERE id='m-1'")
    after = db.execute("SELECT updated_at FROM v2_member WHERE id='m-1'").fetchone()["updated_at"]
    assert after != before


def test_task_updated_at_trigger(db):
    _insert_device(db, "d-1")
    db.execute("INSERT INTO v2_task (id, device_id, intent) VALUES ('t-1', 'd-1', 'draw_image')")
    before = db.execute("SELECT updated_at FROM v2_task WHERE id='t-1'").fetchone()["updated_at"]
    time.sleep(1.1)
    db.execute("UPDATE v2_task SET status='running' WHERE id='t-1'")
    after = db.execute("SELECT updated_at FROM v2_task WHERE id='t-1'").fetchone()["updated_at"]
    assert after != before


def test_voiceprint_updated_at_trigger(db):
    _insert_account(db, "a-1")
    _insert_device(db, "d-1")
    db.execute("INSERT INTO v2_member (id, account_id, device_id, name) VALUES ('m-1', 'a-1', 'd-1', 'child1')")
    db.execute("INSERT INTO v2_voiceprint (id, member_id, device_id) VALUES ('v-1', 'm-1', 'd-1')")
    before = db.execute("SELECT updated_at FROM v2_voiceprint WHERE id='v-1'").fetchone()["updated_at"]
    time.sleep(1.1)
    db.execute("UPDATE v2_voiceprint SET sample_count=5 WHERE id='v-1'")
    after = db.execute("SELECT updated_at FROM v2_voiceprint WHERE id='v-1'").fetchone()["updated_at"]
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
    before = db.execute("SELECT updated_at FROM v2_device_transfer_request WHERE id='tfr-1'").fetchone()["updated_at"]
    time.sleep(1.1)
    db.execute("UPDATE v2_device_transfer_request SET status='accepted' WHERE id='tfr-1'")
    after = db.execute("SELECT updated_at FROM v2_device_transfer_request WHERE id='tfr-1'").fetchone()["updated_at"]
    assert after != before


def test_rma_updated_at_trigger(db):
    _insert_device(db, "d-1")
    db.execute("INSERT INTO v2_device_rma_event (id, device_id, reason) VALUES ('r-1', 'd-1', 'motor failure')")
    before = db.execute("SELECT updated_at FROM v2_device_rma_event WHERE id='r-1'").fetchone()["updated_at"]
    time.sleep(1.1)
    db.execute("UPDATE v2_device_rma_event SET status='in_progress' WHERE id='r-1'")
    after = db.execute("SELECT updated_at FROM v2_device_rma_event WHERE id='r-1'").fetchone()["updated_at"]
    assert after != before


def test_supply_updated_at_trigger(db):
    _insert_device(db, "d-1")
    db.execute("INSERT INTO v2_device_supply (id, device_id, supply_type) VALUES ('s-1', 'd-1', 'pen')")
    before = db.execute("SELECT updated_at FROM v2_device_supply WHERE id='s-1'").fetchone()["updated_at"]
    time.sleep(1.1)
    db.execute("UPDATE v2_device_supply SET level=0.5 WHERE id='s-1'")
    after = db.execute("SELECT updated_at FROM v2_device_supply WHERE id='s-1'").fetchone()["updated_at"]
    assert after != before
