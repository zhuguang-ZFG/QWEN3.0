"""Test date, location, and device context injection."""

import pytest

from context_pipeline.enrich_context import (
    _build_date_context,
    _build_device_context,
    _build_location_context,
    _parse_user_agent,
    inject_enriched_context,
)


class TestDateContext:
    def test_injects_date(self):
        """Date context is always injected."""
        msgs = [{"role": "system", "content": "You are helpful."}]
        result = inject_enriched_context(msgs)
        assert len(result) == 2
        assert "当前时间" in result[1]["content"]
        assert any(w in result[1]["content"] for w in ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"))

    def test_no_system_message(self):
        """Works even without a system message."""
        msgs = [{"role": "user", "content": "hello"}]
        result = inject_enriched_context(msgs)
        assert len(result) == 2
        assert result[0]["role"] == "system"
        assert "当前时间" in result[0]["content"]

    def test_empty_messages(self):
        """Works with empty list."""
        result = inject_enriched_context([])
        assert len(result) == 1

    def test_no_side_effects(self):
        """Original messages are not modified."""
        msgs = [{"role": "system", "content": "hi"}]
        original = [dict(m) for m in msgs]
        _ = inject_enriched_context(msgs)
        assert msgs == original

    def test_build_date_returns_non_empty(self):
        d = _build_date_context()
        assert len(d) > 10
        assert "当前时间" in d


class TestDeviceParsing:
    def test_windows_chrome(self):
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0"
        assert "Windows 10" in _parse_user_agent(ua)
        assert "Chrome" in _parse_user_agent(ua)

    def test_macos_firefox(self):
        ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Firefox/109.0"
        device = _parse_user_agent(ua)
        assert "macOS" in device
        assert "Firefox" in device

    def test_opencode(self):
        ua = "OpenCode/1.0"
        assert _parse_user_agent(ua) == "OpenCode"

    def test_android_mobile(self):
        ua = "Mozilla/5.0 (Linux; Android 13; Pixel 7) Chrome/120.0.0.0 Mobile Safari/537.36"
        device = _parse_user_agent(ua)
        assert "Android" in device
        assert "移动端" in device

    def test_curl(self):
        ua = "curl/7.88.1"
        assert _parse_user_agent(ua) == "curl"

    def test_empty_ua(self):
        assert _parse_user_agent("") == ""
        assert _parse_user_agent(None) == ""

    def test_unknown_device(self):
        assert _parse_user_agent("some-random-string-123") == ""

    def test_build_device_context(self):
        ctx = _build_device_context("Mozilla/5.0 (Windows NT 10.0) Chrome/120")
        assert "用户设备" in ctx
        assert "Windows" in ctx

    def test_build_device_context_empty(self):
        assert _build_device_context("") == ""


class TestLocationContext:
    def test_local_ip_returns_nothing(self):
        """Localhost IP shouldn't inject location."""
        ctx = _build_location_context("127.0.0.1")
        assert ctx == ""

    def test_empty_ip(self):
        ctx = _build_location_context("")
        assert ctx == ""


class TestEnrichedWithIPAndUA:
    def test_full_enrichment(self):
        """With IP and UA, all three contexts are injected."""
        # Use a non-local IP that won't trigger actual API call in test
        msgs = [{"role": "system", "content": "hi"}]
        result = inject_enriched_context(
            msgs,
            client_ip="8.8.8.8",  # Google DNS — will trigger lookup
            user_agent="Mozilla/5.0 (Windows NT 10.0) Chrome/120",
        )
        assert len(result) >= 2
        content = result[1]["content"]
        assert "当前时间" in content
        assert "用户设备" in content
        # Location may or may not be there (depends on ip-api.com availability)

    def test_multiple_system_messages(self):
        """Insert enrichment after the first system message, respecting subsequent ones."""
        msgs = [
            {"role": "system", "content": "sys1"},
            {"role": "user", "content": "u1"},
            {"role": "system", "content": "sys2"},
            {"role": "user", "content": "u2"},
        ]
        result = inject_enriched_context(msgs)
        assert result[0]["role"] == "system"
        assert result[0]["content"] == "sys1"
        assert result[1]["role"] == "system"
        assert "当前时间" in result[1]["content"]
