"""CHECK / UNIQUE / NOT NULL constraint tests."""

import sqlite3

import pytest

from tests.xiaozhi_schema.conftest import _insert_account, _insert_device


# -- CHECK constraints -------------------------------------------------


def test_account_role_check_enforced(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO v2_account (id, phone, role) VALUES ('a-1', '+86-1', 'superadmin')")


def test_account_status_check_enforced(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO v2_account (id, phone, status) VALUES ('a-1', '+86-2', 'banned')")


def test_device_status_check_enforced(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO v2_device (id, device_sn, model, status) VALUES ('d-1', 'SN-001', 'esp32s3_xyz', 'broken')"
        )


def test_binding_mode_check_enforced(db):
    _insert_account(db, "a-1")
    _insert_device(db, "d-1")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO v2_device_binding (id, device_id, account_id, bind_mode) VALUES ('b-1', 'd-1', 'a-1', 'admin')"
        )


def test_task_status_check_enforced(db):
    _insert_device(db, "d-1")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO v2_task (id, device_id, intent, status) VALUES ('t-1', 'd-1', 'draw_image', 'unknown')")


def test_task_source_check_enforced(db):
    _insert_device(db, "d-1")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO v2_task (id, device_id, intent, source) VALUES ('t-1', 'd-1', 'draw_image', 'cli')")


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
    db.execute("INSERT INTO v2_member (id, account_id, device_id, name) VALUES ('m-1', 'a-1', 'd-1', 'test')")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO v2_voiceprint (id, member_id, device_id, status) VALUES ('v-1', 'm-1', 'd-2', 'unknown')"
        )


def test_rma_type_check_enforced(db):
    _insert_device(db, "d-1")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO v2_device_rma_event (id, device_id, rma_type) VALUES ('r-1', 'd-1', 'refund')")


def test_rma_status_check_enforced(db):
    _insert_device(db, "d-1")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO v2_device_rma_event (id, device_id, status) VALUES ('r-1', 'd-1', 'unknown')")


def test_supply_status_check_enforced(db):
    _insert_device(db, "d-1")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO v2_device_supply (id, device_id, supply_type, status) VALUES ('s-1', 'd-1', 'pen', 'critical')"
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
    db.execute("INSERT INTO v2_device (id, device_sn, model) VALUES ('d-1', 'SN-001', 'esp32s3_xyz')")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO v2_device (id, device_sn, model) VALUES ('d-2', 'SN-001', 'esp32c3_mini')")


def test_binding_unique(db):
    _insert_account(db, "a-1")
    _insert_device(db, "d-1")
    db.execute("INSERT INTO v2_device_binding (id, device_id, account_id) VALUES ('b-1', 'd-1', 'a-1')")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO v2_device_binding (id, device_id, account_id) VALUES ('b-2', 'd-1', 'a-1')")


def test_supply_unique_per_device(db):
    _insert_device(db, "d-1")
    db.execute("INSERT INTO v2_device_supply (id, device_id, supply_type) VALUES ('s-1', 'd-1', 'pen')")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO v2_device_supply (id, device_id, supply_type) VALUES ('s-2', 'd-1', 'pen')")
    # Different supply_type on the same device should work
    db.execute("INSERT INTO v2_device_supply (id, device_id, supply_type) VALUES ('s-3', 'd-1', 'paper')")


# -- NOT NULL constraints -----------------------------------------------


def test_device_sn_not_null(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO v2_device (id, model) VALUES ('d-1', 'esp32s3_xyz')")


def test_device_model_not_null(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO v2_device (id, device_sn) VALUES ('d-1', 'SN-001')")


def test_member_name_not_null(db):
    _insert_account(db, "a-1")
    _insert_device(db, "d-1")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO v2_member (id, account_id, device_id) VALUES ('m-1', 'a-1', 'd-1')")


def test_task_intent_not_null(db):
    _insert_device(db, "d-1")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO v2_task (id, device_id) VALUES ('t-1', 'd-1')")


def test_supply_type_not_null(db):
    _insert_device(db, "d-1")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO v2_device_supply (id, device_id) VALUES ('s-1', 'd-1')")


def test_selfcheck_type_not_null(db):
    _insert_device(db, "d-1")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO v2_self_check_event (id, device_id) VALUES ('sc-1', 'd-1')")
