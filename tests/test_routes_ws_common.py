"""Tests for routes/ws_common.py."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from routes import ws_common as ws


def _websocket(scope=None, headers=None) -> MagicMock:
    websocket = MagicMock()
    websocket.scope = scope or {}
    websocket.headers = headers or {}
    return websocket


def test_client_ip_from_scope_client():
    websocket = _websocket(scope={"client": ["192.168.1.2", 12345]})
    assert ws._client_ip_from_websocket(websocket) == "192.168.1.2"


def test_client_ip_from_x_forwarded_for():
    websocket = _websocket(
        scope={"client": None},
        headers={"x-forwarded-for": "10.0.0.1, 10.0.0.2"},
    )
    assert ws._client_ip_from_websocket(websocket) == "10.0.0.1"


def test_client_ip_from_x_real_ip():
    websocket = _websocket(
        scope={"client": None},
        headers={"x-real-ip": "10.0.0.5"},
    )
    assert ws._client_ip_from_websocket(websocket) == "10.0.0.5"


def test_client_ip_defaults_to_localhost():
    websocket = _websocket(scope={"client": None}, headers={})
    assert ws._client_ip_from_websocket(websocket) == "127.0.0.1"


def test_client_ip_prefers_scope_over_headers():
    websocket = _websocket(
        scope={"client": ["192.168.1.2"]},
        headers={"x-forwarded-for": "10.0.0.1"},
    )
    assert ws._client_ip_from_websocket(websocket) == "192.168.1.2"
