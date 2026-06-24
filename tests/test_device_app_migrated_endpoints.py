"""Tests for endpoints migrated from xiaozhi_compat to device_app."""

from __future__ import annotations

import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from device_gateway.store import InMemoryDeviceTaskStore
from device_gateway.tasks import install_task_store_for_tests, reset_tasks_for_tests
from device_logic.activation import reset_activation_store_for_tests
from device_logic.auth import _hash_password, _verify_password, jwt
from device_logic.db import _schema_ready_paths, connect


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
    monkeypatch.setenv("LIMA_DB_PATH", str(tmp_path / "device_app_migrated.db"))
    monkeypatch.setenv("LIMA_JWT_SECRET", "test-secret-minimum-32-bytes-long!!")
    monkeypatch.setenv("LIMA_XIAOZHI_LOGIN_CODE", "000000")
    _schema_ready_paths.clear()
    reset_activation_store_for_tests()
    reset_tasks_for_tests()
    install_task_store_for_tests(InMemoryDeviceTaskStore())

    from routes.device_app_api import router as api_router
    from routes.device_app_auth import router as auth_router

    app = FastAPI()
    app.include_router(api_router)
    app.include_router(auth_router)
    return TestClient(app)


class TestCaptcha:
    def test_get_captcha_returns_png(self, client):
        resp = client.get("/device/v1/app/auth/captcha")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        assert "X-Captcha-Id" in resp.headers


class TestChangePassword:
    def _seed_account(self, account_id: str, role: str, password_hash: str | None = None):
        with connect() as conn:
            conn.execute(
                "INSERT INTO v2_account (id, phone, nickname, role, password_hash) VALUES (?, ?, ?, ?, ?)",
                (account_id, "13000", "test", role, password_hash),
            )
            conn.commit()

    def test_change_password_success(self, client):
        self._seed_account("a-user", "user", _hash_password("oldpass"))
        resp = client.put(
            "/device/v1/app/auth/change-password",
            json={"oldPassword": "oldpass", "newPassword": "newpass123"},
            headers={"Authorization": f"Bearer {_token('a-user', 'user')}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["accountId"] == "a-user"
        with connect() as conn:
            row = conn.execute("SELECT password_hash FROM v2_account WHERE id=?", ("a-user",)).fetchone()
        assert _verify_password("newpass123", row["password_hash"])

    def test_change_password_wrong_old_password(self, client):
        self._seed_account("a-user", "user", _hash_password("oldpass"))
        resp = client.put(
            "/device/v1/app/auth/change-password",
            json={"oldPassword": "wrongpass", "newPassword": "newpass123"},
            headers={"Authorization": f"Bearer {_token('a-user', 'user')}"},
        )
        assert resp.status_code == 400
        assert resp.json()["code"] == 4003

    def test_change_password_missing_fields(self, client):
        self._seed_account("a-user", "user")
        resp = client.put(
            "/device/v1/app/auth/change-password",
            json={"oldPassword": "oldpass"},
            headers={"Authorization": f"Bearer {_token('a-user', 'user')}"},
        )
        assert resp.status_code == 400


class TestManualAddDevice:
    def _seed_admin(self, account_id: str = "a-admin"):
        with connect() as conn:
            conn.execute(
                "INSERT INTO v2_account (id, phone, nickname, role) VALUES (?, ?, ?, ?)",
                (account_id, "13000", "admin", "admin"),
            )
            conn.commit()

    def test_manual_add_device_admin(self, client):
        self._seed_admin()
        resp = client.post(
            "/device/v1/app/devices/manual-add",
            json={"deviceSn": "SN-ADMIN-01", "model": "esp32s3_xyz"},
            headers={"Authorization": f"Bearer {_token('a-admin', 'admin')}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["device"]["deviceSn"] == "SN-ADMIN-01"

    def test_manual_add_device_forbidden_for_user(self, client):
        with connect() as conn:
            conn.execute(
                "INSERT INTO v2_account (id, phone, nickname, role) VALUES (?, ?, ?, ?)",
                ("a-user", "13001", "user", "user"),
            )
            conn.commit()
        resp = client.post(
            "/device/v1/app/devices/manual-add",
            json={"deviceSn": "SN-USER-01"},
            headers={"Authorization": f"Bearer {_token('a-user', 'user')}"},
        )
        assert resp.status_code == 403

    def test_manual_add_device_requires_device_sn(self, client):
        self._seed_admin()
        resp = client.post(
            "/device/v1/app/devices/manual-add",
            json={},
            headers={"Authorization": f"Bearer {_token('a-admin', 'admin')}"},
        )
        assert resp.status_code == 400
