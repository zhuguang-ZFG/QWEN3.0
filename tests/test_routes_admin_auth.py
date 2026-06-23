"""Tests for routes/admin_auth.py."""

from __future__ import annotations

import pytest
from fastapi import Request

from routes import admin_auth as aa


def test_get_admin_token_from_env(monkeypatch):
    monkeypatch.setenv("LIMA_ADMIN_TOKEN", "secret")
    assert aa.get_admin_token() == "secret"


def test_admin_session_value_is_stable(monkeypatch):
    monkeypatch.setenv("LIMA_ADMIN_TOKEN", "secret")
    assert aa.admin_session_value() == aa.admin_session_value()
    assert len(aa.admin_session_value()) == 64


def test_is_valid_admin_session(monkeypatch):
    monkeypatch.setenv("LIMA_ADMIN_TOKEN", "secret")
    assert aa.is_valid_admin_session(aa.admin_session_value()) is True
    assert aa.is_valid_admin_session("wrong") is False
    monkeypatch.setenv("LIMA_ADMIN_TOKEN", "")
    assert aa.is_valid_admin_session(aa.admin_session_value()) is False


@pytest.mark.asyncio
async def test_verify_admin_with_bearer(monkeypatch):
    monkeypatch.setenv("LIMA_ADMIN_TOKEN", "admin-token")
    # header token
    await aa.verify_admin(authorization="Bearer admin-token", lima_admin_session="")


@pytest.mark.asyncio
async def test_verify_admin_with_cookie(monkeypatch):
    monkeypatch.setenv("LIMA_ADMIN_TOKEN", "admin-token")
    cookie = aa.admin_session_value()
    await aa.verify_admin(authorization="", lima_admin_session=cookie)


@pytest.mark.asyncio
async def test_verify_admin_missing_token_returns_503(monkeypatch):
    monkeypatch.setenv("LIMA_ADMIN_TOKEN", "")
    with pytest.raises(Exception) as exc_info:
        await aa.verify_admin(authorization="Bearer admin-token")
    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_verify_admin_bad_token_returns_401(monkeypatch):
    monkeypatch.setenv("LIMA_ADMIN_TOKEN", "admin-token")
    with pytest.raises(Exception) as exc_info:
        await aa.verify_admin(authorization="Bearer wrong", lima_admin_session="")
    assert exc_info.value.status_code == 401


def _request_with_host(host: str) -> Request:
    return Request({"type": "http", "headers": [], "server": (host, 80), "path": "/"})


@pytest.mark.asyncio
async def test_verify_csrf_exempt_with_bearer():
    req = _request_with_host("example.com")
    await aa.verify_csrf(req, authorization="Bearer token", origin="https://evil.com")


@pytest.mark.asyncio
async def test_verify_csrf_matching_origin():
    req = _request_with_host("example.com")
    await aa.verify_csrf(req, authorization="", origin="https://example.com", referer="")


@pytest.mark.asyncio
async def test_verify_csrf_matching_referer():
    req = _request_with_host("example.com")
    await aa.verify_csrf(req, authorization="", origin="", referer="https://example.com/path")


@pytest.mark.asyncio
async def test_verify_csrf_mismatch_raises_403():
    req = _request_with_host("example.com")
    with pytest.raises(Exception) as exc_info:
        await aa.verify_csrf(req, authorization="", origin="https://evil.com", referer="")
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_verify_csrf_missing_host_raises_403():
    req = Request({"type": "http", "headers": [], "path": "/"})
    with pytest.raises(Exception) as exc_info:
        await aa.verify_csrf(req, authorization="", origin="", referer="")
    assert exc_info.value.status_code == 403
