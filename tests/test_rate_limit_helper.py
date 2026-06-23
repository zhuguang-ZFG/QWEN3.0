"""Tests for routes/rate_limit_helper.py — rate limit helpers."""

from unittest.mock import patch

from routes.rate_limit_helper import check_key_limit, _disabled


class TestDisabled:
    def test_disabled(self):
        with patch("routes.rate_limit_helper.SECURITY.rate_limit_disable", True):
            assert _disabled() is True

    def test_enabled(self):
        with patch("routes.rate_limit_helper.SECURITY.rate_limit_disable", False):
            assert _disabled() is False


class TestCheckKeyLimit:
    def test_disabled_returns_none(self):
        with patch("routes.rate_limit_helper.SECURITY.rate_limit_disable", True):
            assert check_key_limit("key", 10) is None

    def test_under_limit(self):
        with patch("routes.rate_limit_helper.SECURITY.rate_limit_disable", False):
            with patch("routes.rate_limit_helper.rate_limiter.check_keyed_rate_limit", return_value=True):
                assert check_key_limit("key", 10) is None

    def test_over_limit(self):
        with patch("routes.rate_limit_helper.SECURITY.rate_limit_disable", False):
            with patch("routes.rate_limit_helper.rate_limiter.check_keyed_rate_limit", return_value=False):
                response = check_key_limit("key", 10)
                assert response.status_code == 429
                assert "rate_limit_error" in response.body.decode()
