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
