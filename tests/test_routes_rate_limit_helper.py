"""Tests for routes/rate_limit_helper.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import Request

from routes import rate_limit_helper as rlh


@pytest.fixture
def mock_request():
    scope = {
        "type": "http",
        "client": ("192.168.1.1", 12345),
        "headers": [],
    }
    return Request(scope)


@patch.object(rlh.SECURITY, "rate_limit_disable", True)
@patch.object(rlh.rate_limiter, "check_keyed_rate_limit")
def test_check_key_limit_disabled(mock_check, mock_request):
    assert rlh.check_key_limit("k", 10) is None
    mock_check.assert_not_called()


@patch.object(rlh.SECURITY, "rate_limit_disable", False)
@patch.object(rlh.rate_limiter, "check_keyed_rate_limit", return_value=True)
def test_check_key_limit_allowed(mock_check):
    assert rlh.check_key_limit("k", 10) is None
    mock_check.assert_called_once_with("k", max_per_window=10, window=60.0)


@patch.object(rlh.SECURITY, "rate_limit_disable", False)
@patch.object(rlh.rate_limiter, "check_keyed_rate_limit", return_value=False)
def test_check_key_limit_exceeded(mock_check):
    resp = rlh.check_key_limit("k", 10)
    assert resp is not None
    assert resp.status_code == 429
    assert "rate_limit_error" in resp.body.decode()


@patch.object(rlh.SECURITY, "rate_limit_disable", False)
@patch.object(rlh.rate_limiter, "check_keyed_rate_limit", return_value=False)
@patch.object(rlh, "client_ip", return_value="1.2.3.4")
def test_check_ip_limit_uses_scoped_key(mock_ip, mock_check, mock_request):
    resp = rlh.check_ip_limit(mock_request, "chat", 5)
    assert resp is not None
    assert resp.status_code == 429
    mock_check.assert_called_once_with("chat:1.2.3.4", max_per_window=5, window=60.0)
