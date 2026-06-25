"""Tests for routes/device_app_auth.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from device_logic import auth as auth_core
from routes import device_app_auth as auth
from routes import device_app_auth_email as email_auth


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("LIMA_XIAOZHI_DEV_STATIC_LOGIN_CODE", "true")
    app = FastAPI()
    app.include_router(auth.router)
    return TestClient(app)


@pytest.fixture
def auth_header():
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def account():
    return {
        "id": "acc-1",
        "phone": "12345678901",
        "email": "tester@example.com",
        "password_hash": "hashed",
        "role": "user",
        "status": "active",
        "nickname": "tester",
        "avatar_url": "",
        "created_at": "2024-01-01T00:00:00Z",
    }


def _make_conn(rows=None):
    conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchone.side_effect = rows or []
    cursor.fetchall.return_value = rows or []
    conn.execute.return_value = cursor
    return conn


@pytest.fixture(autouse=True)
def _patch_deps(account):
    from device_logic import db as db_module
    with patch.object(auth, "authorize", return_value=account), \
         patch.object(auth, "allow_device_auth", return_value=True), \
         patch.object(auth_core, "make_token", return_value="token-123"), \
         patch.object(auth, "validate_login_code", return_value=True), \
         patch.object(auth, "login_code_error", return_value=None), \
         patch.object(auth, "sms_verification_payload", return_value={"code": "123456"}), \
         patch.object(auth, "client_ip", return_value="127.0.0.1"), \
         patch.object(auth, "connect") as mock_connect, \
         patch.object(db_module, "connect") as mock_db_connect, \
         patch.object(auth, "new_id", return_value="new-id"):
        mock_conn = _make_conn([account])
        mock_connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_connect.return_value.__exit__ = MagicMock(return_value=False)
        mock_db_connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_db_connect.return_value.__exit__ = MagicMock(return_value=False)
        yield


def test_login_with_phone_success(client):
    response = client.post("/device/v1/app/auth/login", json={"phone": "12345678901", "code": "123456"})
    assert response.status_code == 200
    data = response.json()
    assert data["token"] == "token-123"
    assert data["accountId"] == "acc-1"


def test_login_missing_code(client):
    response = client.post("/device/v1/app/auth/login", json={"phone": "12345678901"})
    assert response.status_code == 400
    assert "code" in response.json()["message"]


def test_login_invalid_code(client):
    with patch.object(auth, "validate_login_code", return_value=False):
        response = client.post("/device/v1/app/auth/login", json={"phone": "12345678901", "code": "000000"})
    assert response.status_code == 401


def test_login_rate_limited(client):
    with patch.object(auth, "allow_device_auth", return_value=False):
        response = client.post("/device/v1/app/auth/login", json={"phone": "12345678901", "code": "123456"})
    assert response.status_code == 429


def test_login_wechat_dev_mode(client, monkeypatch):
    monkeypatch.setenv("LIMA_XIAOZHI_WECHAT_DEV_LOGIN", "true")
    response = client.post("/device/v1/app/auth/login", json={"code": "wx-code"})
    assert response.status_code == 200
    assert response.json()["token"] == "token-123"


def test_login_wechat_not_configured(client, monkeypatch):
    monkeypatch.delenv("LIMA_XIAOZHI_WECHAT_DEV_LOGIN", raising=False)
    response = client.post("/device/v1/app/auth/login", json={"code": "wx-code"})
    assert response.status_code == 503


def test_register_success(client):
    response = client.post("/device/v1/app/auth/register", json={"phone": "12345678901", "code": "123456"})
    assert response.status_code == 200
    assert response.json()["token"] == "token-123"


def test_register_missing_fields(client):
    response = client.post("/device/v1/app/auth/register", json={"phone": "12345678901"})
    assert response.status_code == 400


def test_sms_verification_success(client):
    response = client.post("/device/v1/app/auth/sms-verification", json={"phone": "12345678901"})
    assert response.status_code == 200
    assert response.json()["code"] == "123456"


def test_sms_verification_missing_phone(client):
    response = client.post("/device/v1/app/auth/sms-verification", json={})
    assert response.status_code == 400


def test_get_me_success(client, auth_header):
    response = client.get("/device/v1/app/auth/me", headers=auth_header)
    assert response.status_code == 200
    assert response.json()["accountId"] == "acc-1"


def test_get_me_unauthorized(client):
    with patch.object(auth, "authorize", return_value=auth.err(401, "Unauthorized", 401)):
        response = client.get("/device/v1/app/auth/me", headers={"Authorization": "Bearer bad"})
    assert response.status_code == 401


def test_delete_account_success(client, auth_header):
    response = client.post("/device/v1/app/auth/account/delete", headers=auth_header)
    assert response.status_code == 200
    assert response.json()["accountId"] == "acc-1"


def test_register_email_success(client):
    with patch.object(email_auth, "_hash_password", return_value="hashed"), \
         patch.object(email_auth, "account_by_email", return_value=None):
        response = client.post("/device/v1/app/auth/register-email", json={"email": "new@example.com", "password": "secret123"})
    assert response.status_code == 200
    assert response.json()["token"] == "token-123"


def test_register_email_invalid_email(client):
    response = client.post("/device/v1/app/auth/register-email", json={"email": "not-an-email", "password": "secret123"})
    assert response.status_code == 400


def test_register_email_weak_password(client):
    response = client.post("/device/v1/app/auth/register-email", json={"email": "new@example.com", "password": "123"})
    assert response.status_code == 400


def test_login_email_success(client, account):
    with patch.object(email_auth, "account_by_email", return_value=account), \
         patch.object(email_auth, "_verify_password", return_value=True):
        response = client.post("/device/v1/app/auth/login-email", json={"email": "tester@example.com", "password": "secret123"})
    assert response.status_code == 200
    data = response.json()
    assert data["token"] == "token-123"
    assert data["accountId"] == "acc-1"


def test_login_email_invalid_password(client, account):
    with patch.object(email_auth, "account_by_email", return_value=account), \
         patch.object(email_auth, "_verify_password", return_value=False):
        response = client.post("/device/v1/app/auth/login-email", json={"email": "tester@example.com", "password": "wrong"})
    assert response.status_code == 401


def test_login_email_missing_fields(client):
    response = client.post("/device/v1/app/auth/login-email", json={"email": "tester@example.com"})
    assert response.status_code == 400
