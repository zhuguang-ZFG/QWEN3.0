"""Tests for routes/device_app_api.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import device_app_api as api


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(api.router)
    return TestClient(app)


@pytest.fixture
def auth_header():
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def account():
    return {"id": "acc-1", "phone": "12345678901", "role": "user"}


@pytest.fixture(autouse=True)
def _patch_deps(account):
    with patch.object(api, "authorize", return_value=account), \
         patch.object(api, "connect") as mock_connect, \
         patch.object(api, "new_activation_code", return_value="code-123"), \
         patch.object(api, "logic_bind_device") as mock_bind, \
         patch.object(api, "list_device_rows", return_value=[]), \
         patch.object(api, "get_device_row", return_value=None), \
         patch.object(api, "update_device_row") as mock_update, \
         patch.object(api, "logic_unbind_device") as mock_unbind, \
         patch.object(api, "check_activation_code", return_value=True), \
         patch.object(api, "validate_device_sn", return_value="SN123"), \
         patch.object(api, "require_device_access", return_value=None):
        conn = MagicMock()
        mock_connect.return_value.__enter__ = MagicMock(return_value=conn)
        mock_connect.return_value.__exit__ = MagicMock(return_value=False)
        # Default device row returned by update_device_row when patched directly.
        row = _make_device_row()
        mock_update.return_value = row
        mock_bind.return_value = {"binding_id": "bind-1", "device_id": "dev-1", "device": row}
        mock_unbind.return_value = None
        yield


def _make_device_row(**overrides):
    return {
        "id": overrides.get("id", "dev-1"),
        "device_sn": overrides.get("device_sn", "SN123"),
        "model": overrides.get("model", "esp32s3_xyz"),
        "firmware_ver": overrides.get("firmware_ver", "1.0"),
        "hardware_ver": overrides.get("hardware_ver", "1.0"),
        "status": overrides.get("status", "active"),
        "last_heartbeat": overrides.get("last_heartbeat", ""),
        "mqtt_topic": overrides.get("mqtt_topic", ""),
        "metadata": overrides.get("metadata", None),
    }


def test_register_device_requires_auth(client, monkeypatch):
    with patch.object(api, "authorize", return_value=api.err(401, "Unauthorized", 401)):
        response = client.post("/device/v1/app/devices/register", json={"macAddress": "aa:bb"})
    assert response.status_code == 401


def test_register_device_success(client, auth_header):
    response = client.post("/device/v1/app/devices/register", json={"macAddress": "aa:bb"}, headers=auth_header)
    assert response.status_code == 200
    data = response.json()
    assert data["activationCode"] == "code-123"
    assert data["expiresIn"] == api.ACTIVATION_TTL_SECONDS


def test_register_device_rate_limited(client, auth_header):
    api._register_limiter.reset_all()
    original_max = api._register_limiter._max_calls
    api._register_limiter._max_calls = 1
    try:
        assert client.post(
            "/device/v1/app/devices/register", json={"macAddress": "aa:bb"}, headers=auth_header
        ).status_code == 200
        response = client.post("/device/v1/app/devices/register", json={"macAddress": "aa:cc"}, headers=auth_header)
        assert response.status_code == 429
    finally:
        api._register_limiter._max_calls = original_max
        api._register_limiter.reset_all()


def test_bind_device_missing_fields(client, auth_header):
    response = client.post("/device/v1/app/devices/bind", json={"deviceSn": "SN123"}, headers=auth_header)
    assert response.status_code == 400


def test_bind_device_invalid_activation(client, auth_header):
    with patch.object(api, "check_activation_code", return_value=False):
        response = client.post(
            "/device/v1/app/devices/bind",
            json={"deviceSn": "SN123", "activationCode": "bad"},
            headers=auth_header,
        )
    assert response.status_code == 400


def test_bind_device_success(client, auth_header):
    response = client.post(
        "/device/v1/app/devices/bind",
        json={"deviceSn": "SN123", "activationCode": "code-123", "model": "x"},
        headers=auth_header,
    )
    assert response.status_code == 200
    assert response.json()["deviceId"] == "dev-1"


def test_list_devices_success(client, auth_header):
    row = _make_device_row()
    with patch.object(api, "list_device_rows", return_value=[row]):
        response = client.get("/device/v1/app/devices", headers=auth_header)
    assert response.status_code == 200
    assert response.json()["count"] == 1


def test_get_device_success(client, auth_header):
    row = _make_device_row()
    with patch.object(api, "get_device_row", return_value=row):
        response = client.get("/device/v1/app/devices/dev-1", headers=auth_header)
    assert response.status_code == 200
    assert response.json()["deviceId"] == "dev-1"


def test_get_device_not_found(client, auth_header):
    response = client.get("/device/v1/app/devices/dev-missing", headers=auth_header)
    assert response.status_code == 404


def test_update_device_success(client, auth_header):
    response = client.put("/device/v1/app/devices/dev-1", json={"model": "new"}, headers=auth_header)
    assert response.status_code == 200


def test_unbind_device_success(client, auth_header):
    response = client.post("/device/v1/app/devices/dev-1/unbind", headers=auth_header)
    assert response.status_code == 200
    assert response.json()["status"] == "unbound"
