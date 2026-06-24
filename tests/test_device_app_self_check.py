"""Tests for device voice self-check and device provisioning endpoints."""

from __future__ import annotations

import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import device_voice
from device_gateway.store import InMemoryDeviceTaskStore
from device_gateway.tasks import install_task_store_for_tests, reset_tasks_for_tests
from device_logic.activation import reset_activation_store_for_tests
from device_logic.auth import jwt


def _token(account_id: str, role: str = "user") -> str:
    now = int(time.time())
    payload = {
        "sub": account_id,
        "account_id": account_id,
        "role": role,
        "iat": now,
        "exp": now + 3600,
    }
    return jwt.encode(payload, "test-secret-minimum-32-bytes-long!!", algorithm="HS256")


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_DB_PATH", str(tmp_path / "device_app_self_check.db"))
    monkeypatch.setenv("LIMA_JWT_SECRET", "test-secret-minimum-32-bytes-long!!")
    monkeypatch.setenv("LIMA_XIAOZHI_LOGIN_CODE", "000000")
    monkeypatch.setenv("LIMA_XIAOZHI_DEV_STATIC_LOGIN_CODE", "1")
    from device_logic.db import _schema_ready_paths

    _schema_ready_paths.clear()
    reset_activation_store_for_tests()
    reset_tasks_for_tests()
    install_task_store_for_tests(InMemoryDeviceTaskStore())

    from routes.device_app_api import router as api_router
    from routes.device_app_auth import router as auth_router
    from routes.device_app_misc import router as misc_router

    app = FastAPI()
    app.include_router(api_router)
    app.include_router(auth_router)
    app.include_router(misc_router)
    return TestClient(app)


class TestDeviceProvision:
    def _login(self, client: TestClient, phone: str = "13000000000") -> str:
        resp = client.post("/device/v1/app/auth/login", json={"phone": phone, "code": "000000"})
        assert resp.status_code == 200
        return resp.json()["token"]

    def test_provision_creates_token(self, client):
        token = self._login(client)
        resp = client.post(
            "/device/v1/app/devices/provision",
            json={"deviceSn": "SN-PROVISION-01", "wifiSsid": "HomeWiFi", "wifiPassword": "secret"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["deviceSn"] == "SN-PROVISION-01"
        assert data["protocol"] == "lima-device-v1"
        assert data["expiresIn"] == 1800
        assert "provisionToken" in data
        assert data["configPayload"]["wifi_ssid"] == "HomeWiFi"

    def test_provision_requires_wifi_ssid(self, client):
        token = self._login(client)
        resp = client.post(
            "/device/v1/app/devices/provision",
            json={"deviceSn": "SN-PROVISION-01"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400

    def test_confirm_binds_device(self, client):
        token = self._login(client)
        provision = client.post(
            "/device/v1/app/devices/provision",
            json={"deviceSn": "SN-CONFIRM-01", "wifiSsid": "HomeWiFi"},
            headers={"Authorization": f"Bearer {token}"},
        ).json()

        resp = client.post(
            "/device/v1/app/devices/provision/confirm",
            json={"provisionToken": provision["provisionToken"], "deviceSn": "SN-CONFIRM-01"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "bound"
        assert data["deviceSn"] == "SN-CONFIRM-01"

    def test_confirm_invalid_token_returns_404(self, client):
        resp = client.post(
            "/device/v1/app/devices/provision/confirm",
            json={"provisionToken": "invalid-token", "deviceSn": "SN-NONE-01"},
        )
        assert resp.status_code == 404

    def test_confirm_mismatched_device_sn_returns_400(self, client):
        token = self._login(client)
        provision = client.post(
            "/device/v1/app/devices/provision",
            json={"deviceSn": "SN-MISMATCH-01", "wifiSsid": "HomeWiFi"},
            headers={"Authorization": f"Bearer {token}"},
        ).json()

        resp = client.post(
            "/device/v1/app/devices/provision/confirm",
            json={"provisionToken": provision["provisionToken"], "deviceSn": "SN-OTHER-01"},
        )
        assert resp.status_code == 400

    def test_confirm_expired_token_returns_400(self, client, monkeypatch):
        token = self._login(client)
        provision = client.post(
            "/device/v1/app/devices/provision",
            json={"deviceSn": "SN-EXPIRED-01", "wifiSsid": "HomeWiFi"},
            headers={"Authorization": f"Bearer {token}"},
        ).json()

        # Move time forward so the token is expired when confirm runs.
        monkeypatch.setattr(
            "routes.device_app_misc.now",
            lambda: "2099-01-01T00:00:00+00:00",
        )
        resp = client.post(
            "/device/v1/app/devices/provision/confirm",
            json={"provisionToken": provision["provisionToken"], "deviceSn": "SN-EXPIRED-01"},
        )
        assert resp.status_code == 400
        assert "expired" in resp.json().get("message", "").lower()

    def test_confirm_already_bound_device_returns_400(self, client):
        first_token = self._login(client, phone="13000000001")
        provision1 = client.post(
            "/device/v1/app/devices/provision",
            json={"deviceSn": "SN-DOUBLE-01", "wifiSsid": "HomeWiFi"},
            headers={"Authorization": f"Bearer {first_token}"},
        ).json()
        resp1 = client.post(
            "/device/v1/app/devices/provision/confirm",
            json={"provisionToken": provision1["provisionToken"], "deviceSn": "SN-DOUBLE-01"},
        )
        assert resp1.status_code == 200

        second_token = self._login(client, phone="13000000002")
        provision2 = client.post(
            "/device/v1/app/devices/provision",
            json={"deviceSn": "SN-DOUBLE-01", "wifiSsid": "HomeWiFi"},
            headers={"Authorization": f"Bearer {second_token}"},
        ).json()
        resp2 = client.post(
            "/device/v1/app/devices/provision/confirm",
            json={"provisionToken": provision2["provisionToken"], "deviceSn": "SN-DOUBLE-01"},
        )
        assert resp2.status_code == 400
        assert "already bound" in resp2.json().get("message", "").lower()


class TestDeviceVoiceSelfCheck:
    def test_self_check_returns_components(self):
        result = device_voice.self_check()
        assert isinstance(result, dict)
        assert set(result.keys()) == {"asr", "tts", "vad", "voiceprint"}
        for value in result.values():
            assert isinstance(value, str)

    def test_self_check_disabled_voice_returns_disabled(self, monkeypatch):
        monkeypatch.setattr(device_voice, "VOICE_ENABLED", False)
        result = device_voice.self_check()
        assert result == {"asr": "disabled", "tts": "disabled", "vad": "disabled", "voiceprint": "disabled"}
