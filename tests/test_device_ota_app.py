"""Tests for the app-facing OTA endpoints."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from device_ota import runtime as ota_runtime
from routes.device_ota import router as device_ota_router
from routes.device_ota_app import router as app_ota_router


def _app_ota_client(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-private-token")
    monkeypatch.delenv("LIMA_DEVICE_OTA_STATE_PATH", raising=False)

    # Canonical reset lives in the OTA domain runtime; route modules are now
    # pure adapters and no longer own the singletons.
    ota_runtime.reset_for_tests()

    import routes.device_ota_app as app_ota_mod

    monkeypatch.setattr(
        app_ota_mod,
        "authorize",
        lambda _header: {"id": "acct_1", "role": "user", "phone": "", "email": ""},
    )
    monkeypatch.setattr(
        app_ota_mod,
        "device_access",
        lambda _conn, _account, _device_id: True,
    )
    monkeypatch.setattr(
        app_ota_mod,
        "get_device_row",
        lambda _conn, _device_id: {"firmware_ver": "1.0.0"},
    )
    monkeypatch.setattr(
        app_ota_mod.registry,
        "get",
        lambda _device_id: None,
    )

    app = FastAPI()
    app.include_router(device_ota_router)
    app.include_router(app_ota_router)
    return TestClient(app)


def test_app_ota_check_no_release(monkeypatch):
    """App check returns no_release when nothing is deployed."""
    client = _app_ota_client(monkeypatch)
    response = client.get(
        "/device/v1/ota/check",
        params={"device_id": "dev-1"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "no_release"
    assert data["current_version"] == "1.0.0"


def test_app_ota_check_available_not_selected(monkeypatch):
    """App check shows available firmware when a release is deployed."""
    client = _app_ota_client(monkeypatch)
    for name in ("tests_passing", "canary_verified", "safety_review"):
        r = client.post(
            "/device/v1/ota/release/criteria",
            headers={"Authorization": "Bearer test-private-token"},
            params={"name": name, "passed": "true"},
        )
        assert r.status_code == 200
    client.post(
        "/device/v1/ota/deploy/v2.0.0",
        headers={"Authorization": "Bearer test-private-token"},
        json={
            "url": "https://example.com/fw.bin",
            "sha256": "a" * 64,
            "signature": "c2ln",
        },
    )

    response = client.get(
        "/device/v1/ota/check",
        params={"device_id": "dev-1"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "available_not_selected"
    assert data["available_version"] == "v2.0.0"
    # H1 fix: unselected devices must NOT receive the firmware payload
    # (url/sha256/signature) from an ongoing canary/gradual rollout.
    assert data["firmware"] is None


def test_app_ota_start_selects_device(monkeypatch):
    """App start adds the device to canary and returns selected status."""
    client = _app_ota_client(monkeypatch)
    for name in ("tests_passing", "canary_verified", "safety_review"):
        r = client.post(
            "/device/v1/ota/release/criteria",
            headers={"Authorization": "Bearer test-private-token"},
            params={"name": name, "passed": "true"},
        )
        assert r.status_code == 200
    client.post(
        "/device/v1/ota/deploy/v2.0.0",
        headers={"Authorization": "Bearer test-private-token"},
        json={
            "url": "https://example.com/fw.bin",
            "sha256": "a" * 64,
            "signature": "c2ln",
        },
    )

    response = client.post(
        "/device/v1/ota/start",
        headers={"Authorization": "Bearer test-token"},
        json={"device_id": "dev-1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["status"] == "available_selected"
    assert data["selected"] is True


def test_app_ota_rollback_removes_device(monkeypatch):
    """App start with rollback=true removes the device from canary."""
    client = _app_ota_client(monkeypatch)
    for name in ("tests_passing", "canary_verified", "safety_review"):
        r = client.post(
            "/device/v1/ota/release/criteria",
            headers={"Authorization": "Bearer test-private-token"},
            params={"name": name, "passed": "true"},
        )
        assert r.status_code == 200
    client.post(
        "/device/v1/ota/deploy/v2.0.0",
        headers={"Authorization": "Bearer test-private-token"},
        json={
            "url": "https://example.com/fw.bin",
            "sha256": "a" * 64,
            "signature": "c2ln",
        },
    )
    client.post(
        "/device/v1/ota/start",
        headers={"Authorization": "Bearer test-token"},
        json={"device_id": "dev-1"},
    )

    response = client.post(
        "/device/v1/ota/start",
        headers={"Authorization": "Bearer test-token"},
        json={"device_id": "dev-1", "rollback": True},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["selected"] is False
    assert data["status"] == "available_not_selected"
