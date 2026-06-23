"""Tests for routes/device_app_misc.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import device_app_misc as misc


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(misc.router)
    return TestClient(app)


@pytest.fixture
def auth_header():
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def account():
    return {"id": "acc-1", "phone": "12345678901", "role": "user"}


def _make_conn(rows=None, fetchone_sequence=None):
    conn = MagicMock()
    cursor = MagicMock()
    if rows is not None:
        cursor.fetchall.return_value = rows
        cursor.fetchone.return_value = rows[0] if rows else None
    elif fetchone_sequence is not None:
        cursor.fetchone.side_effect = fetchone_sequence
    else:
        cursor.fetchall.return_value = []
        cursor.fetchone.return_value = None
    conn.execute.return_value = cursor
    return conn


def _ctx_manager(conn):
    class Ctx:
        def __enter__(self):
            return conn
        def __exit__(self, *args):
            return False
    return Ctx()


def _patch_conn(rows=None, fetchone_sequence=None):
    return patch.object(misc, "connect", return_value=_ctx_manager(_make_conn(rows=rows, fetchone_sequence=fetchone_sequence)))


def _make_transfer_row(**overrides):
    return {
        "id": overrides.get("id", "tr-1"),
        "device_id": overrides.get("device_id", "dev-1"),
        "from_account_id": overrides.get("from_account_id", "acc-1"),
        "to_account_id": overrides.get("to_account_id", "acc-2"),
        "status": overrides.get("status", "pending"),
        "reason": overrides.get("reason", ""),
        "expires_at": overrides.get("expires_at", "2099-01-01T00:00:00Z"),
        "accepted_at": overrides.get("accepted_at", ""),
        "cancelled_at": overrides.get("cancelled_at", ""),
        "created_at": overrides.get("created_at", "2024-01-01T00:00:00Z"),
    }


@pytest.fixture(autouse=True)
def _patch_deps(account):
    with patch.object(misc, "authorize", return_value=account), \
         patch.object(misc, "require_device_access", return_value=None), \
         patch.object(misc, "is_owner", return_value=True), \
         patch.object(misc, "expire_pending_transfers"), \
         patch.object(misc, "new_id", return_value="new-id"):
        yield


def test_request_transfer_success(client, auth_header):
    row = _make_transfer_row()
    with _patch_conn(rows=[row]):
        response = client.post(
            "/device/v1/app/devices/dev-1/transfer",
            json={"toPhone": "12345678902", "reason": "gift"},
            headers=auth_header,
        )
    assert response.status_code == 200
    assert response.json()["status"] == "pending"


def test_request_transfer_not_owner(client, auth_header):
    with patch.object(misc, "is_owner", return_value=False):
        response = client.post(
            "/device/v1/app/devices/dev-1/transfer",
            json={"toPhone": "12345678902"},
            headers=auth_header,
        )
    assert response.status_code == 403


def test_request_transfer_missing_recipient(client, auth_header):
    with _patch_conn():
        response = client.post("/device/v1/app/devices/dev-1/transfer", json={}, headers=auth_header)
    assert response.status_code == 400


def test_list_pending_transfers_success(client, auth_header):
    row = _make_transfer_row()
    with _patch_conn(rows=[row]):
        response = client.get("/device/v1/app/transfers/pending", headers=auth_header)
    assert response.status_code == 200
    assert response.json()["count"] == 1


def test_accept_transfer_success(client, auth_header):
    row = _make_transfer_row(to_account_id="acc-1")
    updated = _make_transfer_row(to_account_id="acc-1", status="accepted")
    with _patch_conn(fetchone_sequence=[row, None, updated]):
        response = client.post("/device/v1/app/transfers/tr-1/accept", headers=auth_header)
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"


def test_accept_transfer_not_recipient(client, auth_header):
    row = _make_transfer_row(to_account_id="acc-2")
    with _patch_conn(fetchone_sequence=[row]):
        response = client.post("/device/v1/app/transfers/tr-1/accept", headers=auth_header)
    assert response.status_code == 403


def test_cancel_transfer_success(client, auth_header):
    row = _make_transfer_row()
    updated = _make_transfer_row(status="cancelled")
    with _patch_conn(fetchone_sequence=[row, updated]):
        response = client.post("/device/v1/app/transfers/tr-1/cancel", headers=auth_header)
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def test_list_self_checks_success(client, auth_header):
    row = {
        "id": "sc-1",
        "device_id": "dev-1",
        "check_type": "battery",
        "result": "ok",
        "details": "",
        "duration_ms": 100,
        "triggered_by": "user",
        "created_at": "2024-01-01T00:00:00Z",
    }
    with _patch_conn(rows=[row]):
        response = client.get("/device/v1/app/devices/dev-1/self-checks", headers=auth_header)
    assert response.status_code == 200
    assert response.json()["count"] == 1


def test_update_supplies_success(client, auth_header):
    row = {
        "id": "sup-1",
        "device_id": "dev-1",
        "supply_type": "battery",
        "level": 0.8,
        "status": "normal",
        "last_replaced": "",
        "next_replacement": "",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }
    with _patch_conn(rows=[row]):
        response = client.put(
            "/device/v1/app/devices/dev-1/supplies",
            json={"supplies": [{"supplyType": "battery", "level": 0.8, "status": "normal"}]},
            headers=auth_header,
        )
    assert response.status_code == 200
    assert response.json()[0]["supplyType"] == "battery"


def test_update_supplies_invalid(client, auth_header):
    response = client.put(
        "/device/v1/app/devices/dev-1/supplies",
        json={"supplies": [{"supplyType": "battery", "level": 2.0, "status": "normal"}]},
        headers=auth_header,
    )
    assert response.status_code == 400


def test_get_supplies_success(client, auth_header):
    row = {
        "id": "sup-1",
        "device_id": "dev-1",
        "supply_type": "battery",
        "level": 0.8,
        "status": "normal",
        "last_replaced": "",
        "next_replacement": "",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }
    with _patch_conn(rows=[row]):
        response = client.get("/device/v1/app/devices/dev-1/supplies", headers=auth_header)
    assert response.status_code == 200
    assert response.json()["count"] == 1
