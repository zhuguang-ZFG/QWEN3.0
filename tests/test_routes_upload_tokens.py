"""Tests for routes/upload_tokens.py."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from routes import upload_tokens as tok


@pytest.fixture(autouse=True)
def _reset_env(monkeypatch):
    monkeypatch.delenv("LIMA_UPLOAD_TOKEN_SECRET", raising=False)
    monkeypatch.delenv("LIMA_JWT_SECRET", raising=False)
    monkeypatch.delenv("LIMA_UPLOAD_PUBLIC_GET", raising=False)
    monkeypatch.delenv("LIMA_UPLOAD_TOKEN_TTL", raising=False)


def test_secret_prefers_upload_token_secret(monkeypatch):
    monkeypatch.setenv("LIMA_UPLOAD_TOKEN_SECRET", "upload-secret")
    monkeypatch.setenv("LIMA_JWT_SECRET", "jwt-secret")
    assert tok._secret() == b"upload-secret"


def test_secret_falls_back_to_jwt_secret(monkeypatch):
    monkeypatch.setenv("LIMA_JWT_SECRET", "jwt-secret")
    assert tok._secret() == b"jwt-secret"


def test_secret_empty_when_unconfigured():
    assert tok._secret() == b""


@pytest.mark.parametrize(
    "value, expected",
    [
        ("1", True),
        ("true", True),
        ("yes", True),
        ("0", False),
        ("false", False),
        ("", False),
    ],
)
def test_public_upload_get_enabled(monkeypatch, value, expected):
    monkeypatch.setenv("LIMA_UPLOAD_PUBLIC_GET", value)
    assert tok.public_upload_get_enabled() is expected


@patch("time.time", return_value=1000)
def test_upload_access_token_format(mock_time, monkeypatch):
    monkeypatch.setenv("LIMA_UPLOAD_TOKEN_SECRET", "secret")
    token = tok.upload_access_token("file.png", ttl_seconds=3600)
    exp, sig = token.split(".", 1)
    assert int(exp) == 4600
    assert len(sig) == 64


@patch("time.time", return_value=1000)
def test_verify_valid_token(mock_time, monkeypatch):
    monkeypatch.setenv("LIMA_UPLOAD_TOKEN_SECRET", "secret")
    token = tok.upload_access_token("file.png", ttl_seconds=3600)
    assert tok.verify_upload_access_token("file.png", token) is True


def test_verify_invalid_token_format():
    assert tok.verify_upload_access_token("file.png", "bad-token") is False


def test_verify_wrong_filename():
    assert tok.verify_upload_access_token("file.png", "1234.sig") is False


@patch("time.time", return_value=5000)
def test_verify_expired_token(mock_time, monkeypatch):
    monkeypatch.setenv("LIMA_UPLOAD_TOKEN_SECRET", "secret")
    with patch("time.time", return_value=1000):
        token = tok.upload_access_token("file.png", ttl_seconds=3600)
    assert tok.verify_upload_access_token("file.png", token) is False


def test_verify_tampered_signature(monkeypatch):
    monkeypatch.setenv("LIMA_UPLOAD_TOKEN_SECRET", "secret")
    token = tok.upload_access_token("file.png", ttl_seconds=3600)
    exp, sig = token.split(".", 1)
    tampered = f"{exp}.{'0' * 64}"
    assert tok.verify_upload_access_token("file.png", tampered) is False


def test_verify_empty_secret_fails():
    assert tok.verify_upload_access_token("file.png", "1234.sig") is False
