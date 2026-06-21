"""Tests for upload access tokens."""

from __future__ import annotations

import time

import pytest

from routes.upload_tokens import upload_access_token, verify_upload_access_token


@pytest.fixture(autouse=True)
def upload_token_secret(monkeypatch):
    monkeypatch.setenv("LIMA_JWT_SECRET", "test-secret-minimum-32-bytes-long!!")
    monkeypatch.delenv("LIMA_UPLOAD_PUBLIC_GET", raising=False)


def test_upload_access_token_round_trip():
    token = upload_access_token("abc123.png", ttl_seconds=3600)
    assert verify_upload_access_token("abc123.png", token)


def test_upload_access_token_rejects_wrong_filename():
    token = upload_access_token("abc123.png", ttl_seconds=3600)
    assert not verify_upload_access_token("other.png", token)


def test_upload_access_token_rejects_expired_token(monkeypatch):
    monkeypatch.setattr(time, "time", lambda: 1_000_000)
    token = upload_access_token("abc123.png", ttl_seconds=10)
    monkeypatch.setattr(time, "time", lambda: 1_000_020)
    assert not verify_upload_access_token("abc123.png", token)
