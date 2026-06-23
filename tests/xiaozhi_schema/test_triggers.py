"""updated_at trigger tests — deterministic clock override replaces sleep()."""

import datetime

from tests.xiaozhi_schema.conftest import _insert_account, _insert_device


class _DatetimeClock:
    """Controllable SQLite ``datetime('now')`` source for fast, deterministic tests."""

    def __init__(self, start: str = "2099-01-01 00:00:00") -> None:
        self._dt = datetime.datetime.fromisoformat(start.replace(" ", "T"))

    def advance(self, seconds: int = 1) -> None:
        self._dt += datetime.timedelta(seconds=seconds)

    def now(self) -> str:
        return self._dt.strftime("%Y-%m-%d %H:%M:%S")

    def __call__(self, arg: str) -> str | None:
        if arg == "now":
            return self.now()
        return arg


def _trigger_exists(db, name: str) -> bool:
    row = db.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name=?", (name,)).fetchone()
    return row is not None


def _freeze_datetime(db, start: str = "2099-01-01 00:00:00") -> _DatetimeClock:
    """Override SQLite ``datetime('now')`` on *db* with a controllable clock.

    Must be called **after** INSERT so that DEFAULT clauses (which require a
    constant expression) are not affected by the user-defined function.
    """
    clock = _DatetimeClock(start)
    db.create_function("datetime", 1, clock)
    return clock


def test_account_updated_at_trigger(db):
    assert _trigger_exists(db, "trg_v2_account_updated")
    db.execute("INSERT INTO v2_account (id, phone) VALUES ('a-1', '+86-1')")
    before = db.execute("SELECT updated_at FROM v2_account WHERE id='a-1'").fetchone()["updated_at"]

    clock = _freeze_datetime(db)
    db.execute("UPDATE v2_account SET nickname='neo' WHERE id='a-1'")
    after = db.execute("SELECT updated_at FROM v2_account WHERE id='a-1'").fetchone()["updated_at"]

    assert after == clock.now()
    assert after != before


def test_device_updated_at_trigger(db):
    assert _trigger_exists(db, "trg_v2_device_updated")
    db.execute("INSERT INTO v2_device (id, device_sn, model) VALUES ('d-1', 'SN-001', 'esp32s3_xyz')")
    before = db.execute("SELECT updated_at FROM v2_device WHERE id='d-1'").fetchone()["updated_at"]

    clock = _freeze_datetime(db)
    db.execute("UPDATE v2_device SET firmware_ver='2.0' WHERE id='d-1'")
    after = db.execute("SELECT updated_at FROM v2_device WHERE id='d-1'").fetchone()["updated_at"]

    assert after == clock.now()
    assert after != before


def test_member_updated_at_trigger(db):
    assert _trigger_exists(db, "trg_v2_member_updated")
    _insert_account(db, "a-1")
    _insert_device(db, "d-1")
    db.execute("INSERT INTO v2_member (id, account_id, device_id, name) VALUES ('m-1', 'a-1', 'd-1', 'child1')")
    before = db.execute("SELECT updated_at FROM v2_member WHERE id='m-1'").fetchone()["updated_at"]

    clock = _freeze_datetime(db)
    db.execute("UPDATE v2_member SET role='parent' WHERE id='m-1'")
    after = db.execute("SELECT updated_at FROM v2_member WHERE id='m-1'").fetchone()["updated_at"]

    assert after == clock.now()
    assert after != before


def test_task_updated_at_trigger(db):
    assert _trigger_exists(db, "trg_v2_task_updated")
    _insert_device(db, "d-1")
    db.execute("INSERT INTO v2_task (id, device_id, intent) VALUES ('t-1', 'd-1', 'draw_image')")
    before = db.execute("SELECT updated_at FROM v2_task WHERE id='t-1'").fetchone()["updated_at"]

    clock = _freeze_datetime(db)
    db.execute("UPDATE v2_task SET status='running' WHERE id='t-1'")
    after = db.execute("SELECT updated_at FROM v2_task WHERE id='t-1'").fetchone()["updated_at"]

    assert after == clock.now()
    assert after != before


def test_voiceprint_updated_at_trigger(db):
    assert _trigger_exists(db, "trg_v2_voiceprint_updated")
    _insert_account(db, "a-1")
    _insert_device(db, "d-1")
    db.execute("INSERT INTO v2_member (id, account_id, device_id, name) VALUES ('m-1', 'a-1', 'd-1', 'child')")
    db.execute("INSERT INTO v2_voiceprint (id, member_id, device_id, embedding) VALUES ('vp-1', 'm-1', 'd-1', x'00')")
    before = db.execute("SELECT updated_at FROM v2_voiceprint WHERE id='vp-1'").fetchone()["updated_at"]

    clock = _freeze_datetime(db)
    db.execute("UPDATE v2_voiceprint SET sample_count=5 WHERE id='vp-1'")
    after = db.execute("SELECT updated_at FROM v2_voiceprint WHERE id='vp-1'").fetchone()["updated_at"]

    assert after == clock.now()
    assert after != before


def test_transfer_updated_at_trigger(db):
    assert _trigger_exists(db, "trg_v2_transfer_updated")
    _insert_account(db, "a-1")
    _insert_account(db, "a-2")
    _insert_device(db, "d-1")
    db.execute(
        "INSERT INTO v2_device_transfer_request (id, device_id, from_account_id, to_account_id) "
        "VALUES ('tr-1', 'd-1', 'a-1', 'a-2')"
    )
    before = db.execute("SELECT updated_at FROM v2_device_transfer_request WHERE id='tr-1'").fetchone()["updated_at"]

    clock = _freeze_datetime(db)
    db.execute("UPDATE v2_device_transfer_request SET status='accepted' WHERE id='tr-1'")
    after = db.execute("SELECT updated_at FROM v2_device_transfer_request WHERE id='tr-1'").fetchone()["updated_at"]

    assert after == clock.now()
    assert after != before


def test_rma_updated_at_trigger(db):
    assert _trigger_exists(db, "trg_v2_rma_updated")
    _insert_account(db, "a-1")
    _insert_device(db, "d-1")
    db.execute("INSERT INTO v2_device_rma_event (id, device_id, rma_type) VALUES ('rma-1', 'd-1', 'repair')")
    before = db.execute("SELECT updated_at FROM v2_device_rma_event WHERE id='rma-1'").fetchone()["updated_at"]

    clock = _freeze_datetime(db)
    db.execute("UPDATE v2_device_rma_event SET status='in_progress' WHERE id='rma-1'")
    after = db.execute("SELECT updated_at FROM v2_device_rma_event WHERE id='rma-1'").fetchone()["updated_at"]

    assert after == clock.now()
    assert after != before


def test_supply_updated_at_trigger(db):
    assert _trigger_exists(db, "trg_v2_supply_updated")
    _insert_account(db, "a-2")
    _insert_device(db, "d-2")
    db.execute("INSERT INTO v2_device_supply (id, device_id, supply_type) VALUES ('s-1', 'd-2', 'ink')")
    before = db.execute("SELECT updated_at FROM v2_device_supply WHERE id='s-1'").fetchone()["updated_at"]

    clock = _freeze_datetime(db)
    db.execute("UPDATE v2_device_supply SET level=0.5 WHERE id='s-1'")
    after = db.execute("SELECT updated_at FROM v2_device_supply WHERE id='s-1'").fetchone()["updated_at"]

    assert after == clock.now()
    assert after != before
