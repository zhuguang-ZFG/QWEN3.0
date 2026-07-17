"""JWT typ gate tests (LIMA_JWT_REQUIRE_TYP / production default)."""

from __future__ import annotations

import logging

import pytest
from fastapi.responses import JSONResponse

import device_logic.auth as auth


@pytest.fixture(autouse=True)
def _ensure_bcrypt():
    if auth.bcrypt is None:
        pytest.skip("bcrypt is not installed")


def test_authorize_rejects_legacy_no_typ_when_required(monkeypatch):
    monkeypatch.setenv("LIMA_JWT_SECRET", "test-secret-for-typ-isolation")
    monkeypatch.setenv("LIMA_JWT_REQUIRE_TYP", "1")
    secret = auth.jwt_secret()
    assert secret is not None
    payload = {
        "sub": "legacy-device-1",
        "account_id": "legacy-device-1",
        "role": "user",
        "iat": 1700000000,
        "exp": 9999999999,
    }
    token = auth.jwt.encode(payload, secret, algorithm="HS256")
    result = auth.authorize(f"Bearer {token}")
    assert isinstance(result, JSONResponse)
    assert result.status_code == 401


def test_authorize_accepts_legacy_no_typ_when_disabled(monkeypatch, caplog):
    monkeypatch.setenv("LIMA_JWT_SECRET", "test-secret-for-typ-isolation")
    monkeypatch.setenv("LIMA_JWT_REQUIRE_TYP", "0")
    caplog.set_level(logging.WARNING)
    secret = auth.jwt_secret()
    assert secret is not None
    payload = {
        "sub": "legacy-device-2",
        "account_id": "legacy-device-2",
        "role": "user",
        "iat": 1700000000,
        "exp": 9999999999,
    }
    token = auth.jwt.encode(payload, secret, algorithm="HS256")
    result = auth.authorize(f"Bearer {token}")
    assert isinstance(result, JSONResponse)
    assert any("legacy" in record.message for record in caplog.records)


def test_decode_admin_token_rejects_legacy_no_typ_when_required(monkeypatch):
    import device_logic.admin_auth as admin_auth

    monkeypatch.setenv("LIMA_JWT_SECRET", "test-secret-for-typ-isolation")
    monkeypatch.setenv("LIMA_JWT_REQUIRE_TYP", "1")
    secret = admin_auth._jwt_secret()
    assert secret is not None
    payload = {
        "sub": "legacy-admin-req",
        "role": "admin",
        "iat": 1700000000,
        "exp": 9999999999,
    }
    token = admin_auth.jwt.encode(payload, secret, algorithm="HS256")
    assert admin_auth.decode_admin_token(token) is None


def test_jwt_require_typ_defaults_on_in_production(monkeypatch):
    monkeypatch.setenv("LIMA_RUNTIME_ENV", "production")
    monkeypatch.delenv("LIMA_JWT_REQUIRE_TYP", raising=False)
    from runtime_env import jwt_require_typ

    assert jwt_require_typ() is True


def test_jwt_require_typ_defaults_off_outside_production(monkeypatch):
    monkeypatch.setenv("LIMA_RUNTIME_ENV", "dev")
    monkeypatch.delenv("LIMA_JWT_REQUIRE_TYP", raising=False)
    from runtime_env import jwt_require_typ

    assert jwt_require_typ() is False
