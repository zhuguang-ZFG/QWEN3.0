"""Tests for healthcheck_ping.py — dead-man ping helpers."""

from unittest.mock import patch

from healthcheck_ping import is_healthcheck_enabled, _normalize_url, ping_healthcheck


class TestIsHealthcheckEnabled:
    def test_disabled_by_default(self):
        with patch.dict("os.environ", {}, clear=True):
            assert is_healthcheck_enabled() is False

    def test_enabled_with_1(self):
        with patch.dict("os.environ", {"LIMA_HEALTHCHECK_ENABLED": "1"}):
            assert is_healthcheck_enabled() is True

    def test_enabled_with_true(self):
        with patch.dict("os.environ", {"LIMA_HEALTHCHECK_ENABLED": "true"}):
            assert is_healthcheck_enabled() is True

    def test_disabled_with_0(self):
        with patch.dict("os.environ", {"LIMA_HEALTHCHECK_ENABLED": "0"}):
            assert is_healthcheck_enabled() is False


class TestNormalizeUrl:
    def test_strips_whitespace(self):
        assert _normalize_url("  https://example.com  ") == "https://example.com"

    def test_strips_trailing_slash(self):
        assert _normalize_url("https://example.com/ping/") == "https://example.com/ping"

    def test_no_change_needed(self):
        assert _normalize_url("https://example.com") == "https://example.com"

    def test_empty_string(self):
        assert _normalize_url("") == ""
