"""Unit tests for device_logic/auth.py password verification and token helpers."""

from __future__ import annotations

import logging

import pytest

import device_logic.auth as auth


@pytest.fixture(autouse=True)
def _ensure_bcrypt():
    """Skip tests when bcrypt is not installed in the test environment."""
    if auth.bcrypt is None:
        pytest.skip("bcrypt is not installed")


def test_hash_and_verify_password_roundtrip():
    hashed = auth._hash_password("secret123")
    assert auth._verify_password("secret123", hashed) is True


def test_verify_password_wrong_password_returns_false():
    hashed = auth._hash_password("secret123")
    assert auth._verify_password("wrong", hashed) is False


def test_verify_password_empty_hash_returns_false():
    assert auth._verify_password("secret123", None) is False
    assert auth._verify_password("secret123", "") is False


def test_verify_password_malformed_hash_logs_warning_and_returns_false(caplog):
    caplog.set_level(logging.WARNING)

    def _raise_valueerror(*_args, **_kwargs):
        raise ValueError("invalid salt")

    monkeypatch = pytest.MonkeyPatch()
    with monkeypatch.context() as m:
        m.setattr(auth.bcrypt, "checkpw", _raise_valueerror)
        assert auth._verify_password("secret123", "not-a-real-hash") is False

    assert any("malformed" in record.message.lower() for record in caplog.records)


def test_verify_password_unexpected_error_logs_error_and_returns_false(caplog):
    caplog.set_level(logging.ERROR)

    def _raise_runtimeerror(*_args, **_kwargs):
        raise RuntimeError("bcrypt internal failure")

    monkeypatch = pytest.MonkeyPatch()
    with monkeypatch.context() as m:
        m.setattr(auth.bcrypt, "checkpw", _raise_runtimeerror)
        assert auth._verify_password("secret123", "$2b$12$...") is False

    assert any("verification encountered an error" in record.message for record in caplog.records)


def test_make_token_requires_jwt(monkeypatch, caplog):
    caplog.set_level(logging.WARNING)
    monkeypatch.setattr(auth, "jwt", None)
    monkeypatch.setattr(auth, "_JWT_IMPORT_ERROR", ImportError("PyJWT is not installed"))

    fake_account = {
        "id": "acc-1",
        "phone": "13000000000",
        "nickname": "n",
        "avatar_url": "",
        "role": "user",
        "created_at": 0,
    }
    assert auth.make_token(fake_account) is None
    assert any("PyJWT is not installed" in record.message for record in caplog.records)


def test_make_token_includes_tv_from_token_epoch(monkeypatch):
    """make_token includes 'tv' (token version) from account token_epoch."""
    monkeypatch.setenv("LIMA_JWT_SECRET", "test-secret-for-token-epoch")
    fake_account = {
        "id": "acc-1",
        "phone": "13000000000",
        "nickname": "n",
        "avatar_url": "",
        "role": "user",
        "created_at": 0,
        "token_epoch": 3,
    }
    token = auth.make_token(fake_account)
    assert token is not None
    decoded = auth.jwt.decode(token, auth.jwt_secret(), algorithms=["HS256"])
    assert decoded["tv"] == 3


def test_make_token_defaults_tv_to_zero_when_missing(monkeypatch):
    """make_token defaults 'tv' to 0 when token_epoch is missing or None."""
    monkeypatch.setenv("LIMA_JWT_SECRET", "test-secret-for-token-epoch")
    fake_account = {
        "id": "acc-1",
        "phone": "13000000000",
        "nickname": "n",
        "avatar_url": "",
        "role": "user",
        "created_at": 0,
    }
    token = auth.make_token(fake_account)
    decoded = auth.jwt.decode(token, auth.jwt_secret(), algorithms=["HS256"])
    assert decoded["tv"] == 0


def test_make_token_includes_typ_device(monkeypatch):
    """make_token includes 'typ': 'device' in the JWT payload."""
    monkeypatch.setenv("LIMA_JWT_SECRET", "test-secret-for-typ-isolation")
    fake_account = {
        "id": "acc-typ-1",
        "phone": "13000000001",
        "nickname": "n",
        "avatar_url": "",
        "role": "user",
        "created_at": 0,
    }
    token = auth.make_token(fake_account)
    assert token is not None
    decoded = auth.jwt.decode(token, auth.jwt_secret(), algorithms=["HS256"])
    assert decoded.get("typ") == "device"


def test_make_admin_token_includes_typ_admin(monkeypatch):
    """make_admin_token includes 'typ': 'admin' in the JWT payload."""
    import device_logic.admin_auth as admin_auth

    monkeypatch.setenv("LIMA_JWT_SECRET", "test-secret-for-typ-isolation")
    fake_user = {
        "id": "admin-typ-1",
        "email": "admin@test.com",
        "nickname": "admin",
        "role": "admin",
        "status": "active",
        "created_at": "2025-01-01",
    }
    token = admin_auth.make_admin_token(fake_user)
    assert token is not None
    decoded = admin_auth.jwt.decode(token, admin_auth._jwt_secret(), algorithms=["HS256"])
    assert decoded.get("typ") == "admin"


def test_decode_admin_token_rejects_device_typ(monkeypatch, caplog):
    """decode_admin_token returns None for tokens with typ=device."""
    import device_logic.admin_auth as admin_auth

    caplog.set_level(logging.WARNING)
    monkeypatch.setenv("LIMA_JWT_SECRET", "test-secret-for-typ-isolation")
    secret = admin_auth._jwt_secret()
    assert secret is not None

    # Craft a device-typed token
    payload = {
        "sub": "device-test-1",
        "role": "admin",
        "typ": "device",
        "iat": 1700000000,
        "exp": 9999999999,
    }
    token = admin_auth.jwt.encode(payload, secret, algorithm="HS256")
    result = admin_auth.decode_admin_token(token)
    assert result is None
    assert any("device-typed" in record.message for record in caplog.records)


def test_decode_admin_token_accepts_admin_typ(monkeypatch):
    """decode_admin_token accepts tokens with typ=admin."""
    import device_logic.admin_auth as admin_auth

    monkeypatch.setenv("LIMA_JWT_SECRET", "test-secret-for-typ-isolation")
    secret = admin_auth._jwt_secret()
    assert secret is not None

    payload = {
        "sub": "admin-test-1",
        "role": "superadmin",
        "typ": "admin",
        "iat": 1700000000,
        "exp": 9999999999,
    }
    token = admin_auth.jwt.encode(payload, secret, algorithm="HS256")
    result = admin_auth.decode_admin_token(token)
    assert result is not None
    assert result["sub"] == "admin-test-1"


def test_decode_admin_token_accepts_legacy_no_typ(monkeypatch, caplog):
    """decode_admin_token accepts legacy tokens without typ field (compatibility)."""
    import device_logic.admin_auth as admin_auth

    caplog.set_level(logging.WARNING)
    monkeypatch.setenv("LIMA_JWT_SECRET", "test-secret-for-typ-isolation")
    secret = admin_auth._jwt_secret()
    assert secret is not None

    # Legacy token: no typ field
    payload = {
        "sub": "legacy-admin-1",
        "role": "admin",
        "iat": 1700000000,
        "exp": 9999999999,
    }
    token = admin_auth.jwt.encode(payload, secret, algorithm="HS256")
    result = admin_auth.decode_admin_token(token)
    assert result is not None
    assert result["sub"] == "legacy-admin-1"
    assert any("legacy" in record.message for record in caplog.records)


def test_authorize_rejects_admin_typ(monkeypatch):
    """authorize() returns 401 JSONResponse for admin-typed tokens."""
    monkeypatch.setenv("LIMA_JWT_SECRET", "test-secret-for-typ-isolation")
    secret = auth.jwt_secret()
    assert secret is not None

    # Craft an admin-typed token
    payload = {
        "sub": "admin-on-device-1",
        "account_id": "admin-on-device-1",
        "role": "admin",
        "typ": "admin",
        "iat": 1700000000,
        "exp": 9999999999,
    }
    token = auth.jwt.encode(payload, secret, algorithm="HS256")
    result = auth.authorize(f"Bearer {token}")
    from fastapi.responses import JSONResponse

    assert isinstance(result, JSONResponse)
    assert result.status_code == 401
