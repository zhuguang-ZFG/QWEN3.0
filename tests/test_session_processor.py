"""Tests for session_memory/processor.py — session memory pipeline."""

from session_memory.processor import _session_id_from_headers


class TestSessionIdFromHeaders:
    def test_deterministic_output(self):
        headers = {"x-forwarded-for": "1.2.3.4", "user-agent": "Mozilla/5.0"}
        id1 = _session_id_from_headers(headers)
        id2 = _session_id_from_headers(headers)
        assert id1 == id2

    def test_different_ip_different_id(self):
        h1 = {"x-forwarded-for": "1.2.3.4", "user-agent": "test"}
        h2 = {"x-forwarded-for": "5.6.7.8", "user-agent": "test"}
        assert _session_id_from_headers(h1) != _session_id_from_headers(h2)

    def test_different_ua_different_id(self):
        h1 = {"x-forwarded-for": "1.2.3.4", "user-agent": "Chrome"}
        h2 = {"x-forwarded-for": "1.2.3.4", "user-agent": "Firefox"}
        assert _session_id_from_headers(h1) != _session_id_from_headers(h2)

    def test_falls_back_to_x_real_ip(self):
        result = _session_id_from_headers({"x-real-ip": "10.0.0.1", "user-agent": "test"})
        assert isinstance(result, str)
        assert len(result) == 16

    def test_unknown_ip(self):
        result = _session_id_from_headers({"user-agent": "test"})
        assert isinstance(result, str)
        assert len(result) == 16

    def test_empty_headers(self):
        result = _session_id_from_headers({})
        assert isinstance(result, str)
        assert len(result) == 16

    def test_string_hex(self):
        result = _session_id_from_headers({"x-forwarded-for": "127.0.0.1", "user-agent": "curl/7.0"})
        assert all(c in "0123456789abcdef" for c in result)
