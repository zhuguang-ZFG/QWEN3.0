"""Tests for routes/request_tracking.py — request tracking helpers."""

from unittest.mock import MagicMock

from routes.request_tracking import _forwarded_for_chain, client_ip, detect_ide


class TestForwardedForChain:
    def test_empty(self):
        assert _forwarded_for_chain("") == []

    def test_single(self):
        assert _forwarded_for_chain("1.1.1.1") == ["1.1.1.1"]

    def test_multiple(self):
        assert _forwarded_for_chain("1.1.1.1, 2.2.2.2") == ["1.1.1.1", "2.2.2.2"]


class TestClientIp:
    def test_direct_untrusted(self):
        req = MagicMock()
        req.client.host = "8.8.8.8"
        req.headers = {}
        assert client_ip(req) == "8.8.8.8"

    def test_trusted_with_xff(self):
        req = MagicMock()
        req.client.host = "127.0.0.1"
        req.headers = {"x-forwarded-for": "8.8.8.8"}
        assert client_ip(req) == "8.8.8.8"

    def test_cf_ip(self):
        req = MagicMock()
        req.client.host = "127.0.0.1"
        req.headers = {"cf-connecting-ip": "1.2.3.4"}
        assert client_ip(req) == "1.2.3.4"


class TestDetectIde:
    def test_claude(self):
        assert detect_ide([{"content": "using Claude Code"}]) == "Claude Code"

    def test_cursor(self):
        assert detect_ide([{"content": "from Cursor"}]) == "Cursor"

    def test_unknown(self):
        assert detect_ide([{"content": "hello"}]) == ""
