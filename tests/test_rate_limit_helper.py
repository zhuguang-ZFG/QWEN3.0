"""Tests for routes/rate_limit_helper.py — rate limit helpers."""

from unittest.mock import patch

from routes.rate_limit_helper import check_key_limit, _disabled


class TestDisabled:
    def test_disabled_by_env(self):
        with patch.dict("os.environ", {"LIMA_RATE_LIMIT_DISABLE": "1"}):
            assert _disabled() is True

    def test_enabled_by_default(self):
        with patch.dict("os.environ", {}, clear=True):
            assert _disabled() is False


class TestCheckKeyLimit:
    def test_disabled_returns_none(self):
        with patch.dict("os.environ", {"LIMA_RATE_LIMIT_DISABLE": "true"}):
            assert check_key_limit("key", 10) is None

    def test_under_limit(self):
        with patch.dict("os.environ", {}, clear=True):
            with patch("routes.rate_limit_helper.rate_limiter.check_keyed_rate_limit", return_value=True):
                assert check_key_limit("key", 10) is None

    def test_over_limit(self):
        with patch.dict("os.environ", {}, clear=True):
            with patch("routes.rate_limit_helper.rate_limiter.check_keyed_rate_limit", return_value=False):
                response = check_key_limit("key", 10)
                assert response.status_code == 429
                assert "rate_limit_error" in response.body.decode()
