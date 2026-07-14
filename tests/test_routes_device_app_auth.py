"""Tests for routes/device_app_auth.py.

手机号+短信鉴权（register/sms-verification/captcha、login 的 phone 分支）于
2026-07-02 slimdown P2-16 移除。本文件保留微信登录、me、delete、change-password
以及邮箱鉴权（device_app_auth_email）的测试。
API key 路由（device_app_auth_keys）于 2026-07-14 下线（只发不认的死功能）。
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from device_logic import auth as auth_core
import rate_limiter
from routes import device_app_auth as auth
from routes import device_app_auth_email as email_auth


@pytest.fixture
def client(monkeypatch):
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

    rate_limiter.reset()
    with (
        patch.object(auth, "authorize", return_value=account),
        patch.object(auth, "allow_device_auth", return_value=True),
        patch.object(auth_core, "make_token", return_value="token-123"),
        patch.object(auth, "client_ip", return_value="127.0.0.1"),
        patch.object(auth, "connect") as mock_connect,
        patch.object(db_module, "connect") as mock_db_connect,
        patch.object(auth, "new_id", return_value="new-id"),
    ):
        mock_conn = _make_conn([account])
        mock_connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_connect.return_value.__exit__ = MagicMock(return_value=False)
        mock_db_connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_db_connect.return_value.__exit__ = MagicMock(return_value=False)
        yield


def test_login_missing_code(client):
    response = client.post("/device/v1/app/auth/login", json={"phone": "12345678901"})
    assert response.status_code == 400
    assert "code" in response.json()["message"]


def test_login_rate_limited(client):
    with patch.object(auth, "allow_device_auth", return_value=False):
        response = client.post("/device/v1/app/auth/login", json={"code": "wx-code"})
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
    with (
        patch.object(email_auth, "_hash_password", return_value="hashed"),
        patch.object(email_auth, "account_by_email", return_value=None),
    ):
        response = client.post(
            "/device/v1/app/auth/register-email", json={"email": "new@example.com", "password": "secret123"}
        )
    assert response.status_code == 200
    assert response.json()["token"] == "token-123"


def test_register_email_invalid_email(client):
    response = client.post(
        "/device/v1/app/auth/register-email", json={"email": "not-an-email", "password": "secret123"}
    )
    assert response.status_code == 400


def test_register_email_weak_password(client):
    response = client.post("/device/v1/app/auth/register-email", json={"email": "new@example.com", "password": "123"})
    assert response.status_code == 400


def test_login_email_success(client, account):
    with (
        patch.object(email_auth, "account_by_email", return_value=account),
        patch.object(email_auth, "_verify_password", return_value=True),
    ):
        response = client.post(
            "/device/v1/app/auth/login-email", json={"email": "tester@example.com", "password": "secret123"}
        )
    assert response.status_code == 200
    data = response.json()
    assert data["token"] == "token-123"
    assert data["accountId"] == "acc-1"


def test_login_email_invalid_password(client, account):
    with (
        patch.object(email_auth, "account_by_email", return_value=account),
        patch.object(email_auth, "_verify_password", return_value=False),
    ):
        response = client.post(
            "/device/v1/app/auth/login-email", json={"email": "tester@example.com", "password": "wrong"}
        )
    assert response.status_code == 401


def test_login_email_missing_fields(client):
    response = client.post("/device/v1/app/auth/login-email", json={"email": "tester@example.com"})
    assert response.status_code == 400


def test_change_password_increments_token_epoch(client, auth_header, account):
    """改密成功后 token_epoch 递增，旧 token 失效。"""
    with (
        patch.object(auth, "_verify_password", return_value=True),
        patch.object(auth, "_hash_password", return_value="new-hash"),
        patch.object(auth, "connect") as mock_connect,
    ):
        mock_conn = MagicMock()
        mock_connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_connect.return_value.__exit__ = MagicMock(return_value=False)

        response = client.put(
            "/device/v1/app/auth/change-password",
            headers=auth_header,
            json={"oldPassword": "old", "newPassword": "newpass123"},
        )
    assert response.status_code == 200

    # Verify the SQL includes token_epoch increment
    update_calls = [c for c in mock_conn.execute.call_args_list if "token_epoch" in str(c)]
    assert len(update_calls) > 0, "change_password SQL should update token_epoch"


def test_authorize_rejects_token_with_stale_token_epoch(monkeypatch):
    """authorize 拒绝 token_epoch 不匹配的旧 token（改密后旧 token 失效）。"""
    monkeypatch.setenv("LIMA_JWT_SECRET", "test-secret-stale-epoch")
    import device_logic.auth as auth_mod

    # Build a token with tv=0, but set db token_epoch=1
    fake_account = {
        "id": "acc-epoch",
        "phone": "13000000000",
        "nickname": "n",
        "avatar_url": "",
        "role": "user",
        "created_at": 0,
        "token_epoch": 0,
        "status": "active",
    }
    token = auth_mod.make_token(fake_account)
    assert token is not None

    # Mock DB to return row with token_epoch=1
    class _FakeRow:
        def __init__(self, d):
            self._d = d

        def __getitem__(self, key):
            return self._d.get(key)

        def keys(self):
            return self._d.keys()

        def __contains__(self, key):
            return key in self._d

    row_with_epoch_1 = _FakeRow({**fake_account, "token_epoch": 1})
    cursor = MagicMock()
    cursor.fetchone.return_value = row_with_epoch_1
    conn = MagicMock()
    conn.execute.return_value = cursor
    with patch.object(auth_mod, "connect") as mock_connect:
        mock_connect.return_value.__enter__ = MagicMock(return_value=conn)
        mock_connect.return_value.__exit__ = MagicMock(return_value=False)
        result = auth_mod.authorize(f"Bearer {token}")

    from fastapi.responses import JSONResponse

    assert isinstance(result, JSONResponse), "stale token_epoch should return 401"
    assert result.status_code == 401
