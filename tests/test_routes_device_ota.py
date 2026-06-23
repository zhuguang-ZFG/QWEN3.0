"""Tests for routes/device_ota.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import device_ota as ota


@pytest.fixture(autouse=True)
def _reset_ota_state():
    ota.reset_ota_state_for_tests()
    yield
    ota.reset_ota_state_for_tests()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-key")
    monkeypatch.setenv("LIMA_DEVICE_TOKENS", "dev-1=token-1")
    app = FastAPI()
    app.include_router(ota.router)
    return TestClient(app)


# ── Release gate ─────────────────────────────────────────────────────────


def test_release_status_requires_auth(client):
    assert client.get("/device/v1/ota/release/status").status_code == 401


def test_release_status(client):
    response = client.get("/device/v1/ota/release/status", headers={"Authorization": "Bearer test-key"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is False
    assert "criteria" in payload


def test_set_criteria(client):
    response = client.post(
        "/device/v1/ota/release/criteria?name=tests_passing&passed=true",
        headers={"Authorization": "Bearer test-key"},
    )
    assert response.status_code == 200
    assert response.json()["passed"] is True


def test_set_unknown_criteria(client):
    response = client.post(
        "/device/v1/ota/release/criteria?name=unknown&passed=true",
        headers={"Authorization": "Bearer test-key"},
    )
    assert response.status_code == 400


def test_deploy_blocked_when_not_ready(client):
    response = client.post(
        "/device/v1/ota/deploy/v1.2.3",
        headers={"Authorization": "Bearer test-key"},
    )
    assert response.status_code == 412


def test_deploy_success_when_ready(client):
    gate = ota.get_release_gate()
    for name in gate.criteria:
        gate.set_criteria(name, True)
    response = client.post(
        "/device/v1/ota/deploy/v1.2.3",
        headers={"Authorization": "Bearer test-key"},
    )
    assert response.status_code == 200
    assert response.json()["version"] == "v1.2.3"


def test_deploy_with_firmware_metadata(client):
    gate = ota.get_release_gate()
    for name in gate.criteria:
        gate.set_criteria(name, True)
    body = {
        "url": "https://example.com/fw.bin",
        "sha256": "a" * 64,
        "signature": "sig",
    }
    response = client.post(
        "/device/v1/ota/deploy/v1.2.3",
        json=body,
        headers={"Authorization": "Bearer test-key"},
    )
    assert response.status_code == 200
    assert response.json()["firmware"]["url"] == "https://example.com/fw.bin"


def test_deploy_with_bad_firmware_url(client):
    gate = ota.get_release_gate()
    for name in gate.criteria:
        gate.set_criteria(name, True)
    response = client.post(
        "/device/v1/ota/deploy/v1.2.3",
        json={"url": "http://insecure.com/fw.bin", "sha256": "a" * 64, "signature": "sig"},
        headers={"Authorization": "Bearer test-key"},
    )
    assert response.status_code == 400


# ── Canary ───────────────────────────────────────────────────────────────


def test_canary_status_requires_auth(client):
    assert client.get("/device/v1/ota/canary/status").status_code == 401


def test_canary_status(client):
    response = client.get("/device/v1/ota/canary/status", headers={"Authorization": "Bearer test-key"})
    assert response.status_code == 200
    assert "canary_devices" in response.json()


def test_add_and_remove_canary_device(client):
    response = client.post(
        "/device/v1/ota/canary/devices/dev-1",
        headers={"Authorization": "Bearer test-key"},
    )
    assert response.status_code == 200
    assert response.json()["device_id"] == "dev-1"

    response = client.delete(
        "/device/v1/ota/canary/devices/dev-1",
        headers={"Authorization": "Bearer test-key"},
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_record_canary_success(client):
    canary = ota.get_canary()
    canary.add_canary_device("dev-1")
    response = client.post(
        "/device/v1/ota/canary/record-success/dev-1",
        headers={"Authorization": "Bearer test-key"},
    )
    assert response.status_code == 200
    assert response.json()["success_count"] == 1


def test_record_canary_failure(client):
    canary = ota.get_canary()
    canary.add_canary_device("dev-1")
    response = client.post(
        "/device/v1/ota/canary/record-failure/dev-1",
        headers={"Authorization": "Bearer test-key"},
    )
    assert response.status_code == 200
    assert response.json()["failure_count"] == 1


# ── Device-facing ────────────────────────────────────────────────────────


def test_upgrade_plan_missing_device_id(client):
    response = client.post("/device/v1/ota/upgrade-plan", json={})
    assert response.status_code == 400


def test_upgrade_plan_unauthorized(client):
    response = client.post("/device/v1/ota/upgrade-plan", json={"device_id": "dev-1"})
    assert response.status_code == 401


def test_upgrade_plan_no_firmware(client):
    response = client.post(
        "/device/v1/ota/upgrade-plan",
        json={"device_id": "dev-1", "current_version": "v1.0.0"},
        headers={"Authorization": "Bearer token-1"},
    )
    assert response.status_code == 200
    assert response.json()["firmware"] is None


def test_upgrade_plan_with_firmware(client):
    canary = ota.get_canary()
    canary.add_canary_device("dev-1")
    canary.deploy_version("v1.2.3", {"version": "v1.2.3", "url": "https://example.com/fw.bin"})
    response = client.post(
        "/device/v1/ota/upgrade-plan",
        json={"device_id": "dev-1", "current_version": "v1.0.0"},
        headers={"Authorization": "Bearer token-1"},
    )
    assert response.status_code == 200
    assert response.json()["firmware"]["version"] == "v1.2.3"


def test_install_result_not_canary(client):
    response = client.post(
        "/device/v1/ota/install-result",
        json={"device_id": "dev-1", "success": True},
        headers={"Authorization": "Bearer token-1"},
    )
    assert response.status_code == 403


def test_install_result_success(client):
    canary = ota.get_canary()
    canary.add_canary_device("dev-1")
    response = client.post(
        "/device/v1/ota/install-result",
        json={"device_id": "dev-1", "success": True},
        headers={"Authorization": "Bearer token-1"},
    )
    assert response.status_code == 200
    assert response.json()["success_count"] == 1
