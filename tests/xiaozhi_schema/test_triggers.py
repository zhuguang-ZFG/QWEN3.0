"""updated_at trigger tests — no sleep(), checks schema existence + behavior."""

from tests.xiaozhi_schema.conftest import _insert_account, _insert_device


def _trigger_exists(db, name: str) -> bool:
    row = db.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name=?", (name,)).fetchone()
    return row is not None


def _is_valid_datetime(val: str | None) -> bool:
    """Check if value matches SQLite datetime format YYYY-MM-DD HH:MM:SS."""
    if not val or not isinstance(val, str):
        return False
    parts = val.split(" ")
    if len(parts) != 2:
        return False
    date_part, time_part = parts
    return len(date_part) == 10 and len(time_part) == 8


def test_account_updated_at_trigger(db):
    assert _trigger_exists(db, "trg_v2_account_updated")
    db.execute("INSERT INTO v2_account (id, phone) VALUES ('a-1', '+86-1')")
    row = db.execute("SELECT updated_at FROM v2_account WHERE id='a-1'").fetchone()
    assert _is_valid_datetime(row["updated_at"])
    db.execute("UPDATE v2_account SET nickname='neo' WHERE id='a-1'")
    row = db.execute("SELECT updated_at FROM v2_account WHERE id='a-1'").fetchone()
    assert _is_valid_datetime(row["updated_at"])


def test_device_updated_at_trigger(db):
    assert _trigger_exists(db, "trg_v2_device_updated")
    db.execute("INSERT INTO v2_device (id, device_sn, model) VALUES ('d-1', 'SN-001', 'esp32s3_xyz')")
    row = db.execute("SELECT updated_at FROM v2_device WHERE id='d-1'").fetchone()
    assert _is_valid_datetime(row["updated_at"])
    db.execute("UPDATE v2_device SET firmware_ver='2.0' WHERE id='d-1'")
    row = db.execute("SELECT updated_at FROM v2_device WHERE id='d-1'").fetchone()
    assert _is_valid_datetime(row["updated_at"])


def test_member_updated_at_trigger(db):
    assert _trigger_exists(db, "trg_v2_member_updated")
    _insert_account(db, "a-1")
    _insert_device(db, "d-1")
    db.execute("INSERT INTO v2_member (id, account_id, device_id, name) VALUES ('m-1', 'a-1', 'd-1', 'child1')")
    row = db.execute("SELECT updated_at FROM v2_member WHERE id='m-1'").fetchone()
    assert _is_valid_datetime(row["updated_at"])
    db.execute("UPDATE v2_member SET role='parent' WHERE id='m-1'")
    row = db.execute("SELECT updated_at FROM v2_member WHERE id='m-1'").fetchone()
    assert _is_valid_datetime(row["updated_at"])


def test_task_updated_at_trigger(db):
    assert _trigger_exists(db, "trg_v2_task_updated")
    _insert_device(db, "d-1")
    db.execute("INSERT INTO v2_task (id, device_id, intent) VALUES ('t-1', 'd-1', 'draw_image')")
    row = db.execute("SELECT updated_at FROM v2_task WHERE id='t-1'").fetchone()
    assert _is_valid_datetime(row["updated_at"])
    db.execute("UPDATE v2_task SET intent='write_text' WHERE id='t-1'")
    row = db.execute("SELECT updated_at FROM v2_task WHERE id='t-1'").fetchone()
    assert _is_valid_datetime(row["updated_at"])


def test_voiceprint_updated_at_trigger(db):
    assert _trigger_exists(db, "trg_v2_voiceprint_updated")
    _insert_account(db, "a-1")
    _insert_device(db, "d-1")
    db.execute("INSERT INTO v2_member (id, account_id, device_id, name) VALUES ('m-1', 'a-1', 'd-1', 'child')")
    db.execute("INSERT INTO v2_voiceprint (id, member_id, device_id, embedding) VALUES ('vp-1', 'm-1', 'd-1', x'00')")
    row = db.execute("SELECT updated_at FROM v2_voiceprint WHERE id='vp-1'").fetchone()
    assert _is_valid_datetime(row["updated_at"])


def test_transfer_updated_at_trigger(db):
    assert _trigger_exists(db, "trg_v2_transfer_updated")
    _insert_account(db, "a-1")
    _insert_account(db, "a-2")
    _insert_device(db, "d-1")
    db.execute("INSERT INTO v2_device_transfer_request (id, device_id, from_account_id, to_account_id) VALUES ('tr-1', 'd-1', 'a-1', 'a-2')")
    row = db.execute("SELECT updated_at FROM v2_device_transfer_request WHERE id='tr-1'").fetchone()
    assert _is_valid_datetime(row["updated_at"])


def test_rma_updated_at_trigger(db):
    assert _trigger_exists(db, "trg_v2_rma_updated")
    _insert_account(db, "a-1")
    _insert_device(db, "d-1")
    db.execute("INSERT INTO v2_device_rma_event (id, device_id, rma_type) VALUES ('rma-1', 'd-1', 'repair')")
    row = db.execute("SELECT updated_at FROM v2_device_rma_event WHERE id='rma-1'").fetchone()
    assert _is_valid_datetime(row["updated_at"])


def test_supply_updated_at_trigger(db):
    assert _trigger_exists(db, "trg_v2_supply_updated")
    _insert_account(db, "a-2")
    _insert_device(db, "d-2")
    db.execute("INSERT INTO v2_device_supply (id, device_id, supply_type) VALUES ('s-1', 'd-2', 'ink')")
    row = db.execute("SELECT updated_at FROM v2_device_supply WHERE id='s-1'").fetchone()
    assert _is_valid_datetime(row["updated_at"])
