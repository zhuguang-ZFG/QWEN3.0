"""Tests for routes/device_app_members.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import device_app_members as members


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(members.router)
    return TestClient(app)


@pytest.fixture
def auth_header():
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def account():
    return {"id": "acc-1", "phone": "12345678901", "role": "user"}


def _make_member_row(**overrides):
    return {
        "id": overrides.get("id", "mem-1"),
        "account_id": overrides.get("account_id", "acc-1"),
        "device_id": overrides.get("device_id", "dev-1"),
        "name": overrides.get("name", "Alice"),
        "role": overrides.get("role", "child"),
        "avatar_url": overrides.get("avatar_url", ""),
        "voiceprint_id": overrides.get("voiceprint_id", ""),
        "status": overrides.get("status", "active"),
        "created_at": overrides.get("created_at", "2024-01-01T00:00:00Z"),
    }


def _make_voiceprint_row(**overrides):
    return {
        "id": overrides.get("id", "vp-1"),
        "member_id": overrides.get("member_id", "mem-1"),
        "device_id": overrides.get("device_id", "dev-1"),
        "audio_id": overrides.get("audio_id", "aid-1"),
        "label": overrides.get("label", ""),
        "introduce": overrides.get("introduce", ""),
        "sample_count": overrides.get("sample_count", 0),
        "confidence": overrides.get("confidence", 0.0),
        "status": overrides.get("status", "verifying"),
        "created_at": overrides.get("created_at", "2024-01-01T00:00:00Z"),
    }


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


def _patch_conn(rows=None, fetchone_sequence=None):
    conn = _make_conn(rows=rows, fetchone_sequence=fetchone_sequence)
    return patch.object(members, "connect", return_value=_ctx_manager(conn))


def _ctx_manager(conn):
    class Ctx:
        def __enter__(self):
            return conn
        def __exit__(self, *args):
            return False
    return Ctx()


@pytest.fixture(autouse=True)
def _patch_deps(account):
    with patch.object(members, "authorize", return_value=account), \
         patch.object(members, "require_device_access", return_value=None), \
         patch.object(members, "ALLOWED_MEMBER_ROLES", {"child", "adult", "admin"}), \
         patch.object(members, "new_id", return_value="new-id"):
        yield


def test_create_member_success(client, auth_header):
    with _patch_conn(rows=[_make_member_row()]):
        response = client.post(
            "/device/v1/app/members",
            json={"deviceId": "dev-1", "name": "Alice", "role": "child"},
            headers=auth_header,
        )
    assert response.status_code == 200
    assert response.json()["name"] == "Alice"


def test_create_member_missing_fields(client, auth_header):
    response = client.post("/device/v1/app/members", json={"deviceId": "dev-1"}, headers=auth_header)
    assert response.status_code == 400


def test_create_member_invalid_role(client, auth_header):
    response = client.post(
        "/device/v1/app/members",
        json={"deviceId": "dev-1", "name": "Alice", "role": "robot"},
        headers=auth_header,
    )
    assert response.status_code == 400


def test_list_members_success(client, auth_header):
    with _patch_conn(rows=[_make_member_row()]):
        response = client.get("/device/v1/app/devices/dev-1/members", headers=auth_header)
    assert response.status_code == 200
    assert response.json()["count"] == 1


def test_enroll_voiceprint_success(client, auth_header):
    member = _make_member_row()
    voiceprint = _make_voiceprint_row()
    with _patch_conn(fetchone_sequence=[member, None, voiceprint]):
        response = client.post(
            "/device/v1/app/voiceprints/enroll",
            json={"memberId": "mem-1", "deviceId": "dev-1", "audioId": "aid-1"},
            headers=auth_header,
        )
    assert response.status_code == 200
    assert response.json()["memberId"] == "mem-1"


def test_enroll_voiceprint_member_not_found(client, auth_header):
    with _patch_conn(fetchone_sequence=[None]):
        response = client.post(
            "/device/v1/app/voiceprints/enroll",
            json={"memberId": "mem-1", "deviceId": "dev-1", "audioId": "aid-1"},
            headers=auth_header,
        )
    assert response.status_code == 404


def test_list_voiceprints_success(client, auth_header):
    row = _make_voiceprint_row()
    row["member_name"] = "Alice"
    with _patch_conn(rows=[row]):
        response = client.get("/device/v1/app/devices/dev-1/voiceprints", headers=auth_header)
    assert response.status_code == 200
    assert response.json()["count"] == 1


def test_update_voiceprint_success(client, auth_header):
    row = _make_voiceprint_row()
    with _patch_conn(fetchone_sequence=[row, row]):
        response = client.put(
            "/device/v1/app/voiceprints/vp-1",
            json={"sourceName": "Alice", "introduce": "hello"},
            headers=auth_header,
        )
    assert response.status_code == 200


def test_update_voiceprint_not_found(client, auth_header):
    with _patch_conn(fetchone_sequence=[None]):
        response = client.put(
            "/device/v1/app/voiceprints/vp-1",
            json={"sourceName": "Alice"},
            headers=auth_header,
        )
    assert response.status_code == 404


def test_delete_voiceprint_success(client, auth_header):
    row = _make_voiceprint_row()
    with _patch_conn(fetchone_sequence=[row]):
        response = client.delete("/device/v1/app/voiceprints/vp-1", headers=auth_header)
    assert response.status_code == 200
    assert response.json()["status"] == "disabled"
