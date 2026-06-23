"""Tests for routes/ws_common.py — WebSocket helpers."""

from unittest.mock import MagicMock

from routes.ws_common import _client_ip_from_websocket


class TestClientIpFromWebsocket:
    def test_client_from_scope(self):
        ws = MagicMock()
        ws.scope = {"client": ["192.168.1.2", 12345]}
        ws.headers = {}
        assert _client_ip_from_websocket(ws) == "192.168.1.2"

    def test_forwarded_header(self):
        ws = MagicMock()
        ws.scope = {}
        ws.headers = {"x-forwarded-for": "10.0.0.1, 10.0.0.2"}
        assert _client_ip_from_websocket(ws) == "10.0.0.1"

    def test_real_ip_header(self):
        ws = MagicMock()
        ws.scope = {}
        ws.headers = {"x-real-ip": "172.16.0.1"}
        assert _client_ip_from_websocket(ws) == "172.16.0.1"

    def test_default(self):
        ws = MagicMock()
        ws.scope = {}
        ws.headers = {}
        assert _client_ip_from_websocket(ws) == "127.0.0.1"
