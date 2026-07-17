"""Tests for routes/rate_limit_helper.py — rate limit helpers."""

from unittest.mock import patch

from routes.rate_limit_helper import check_key_limit, _disabled


class TestDisabled:
    def test_disabled(self):
        with patch("routes.rate_limit_helper.rate_limit_disabled", return_value=True):
            assert _disabled() is True

    def test_enabled(self):
        with patch("routes.rate_limit_helper.rate_limit_disabled", return_value=False):
            assert _disabled() is False

    def test_production_ignores_disable_flag(self, monkeypatch):
        monkeypatch.setenv("LIMA_RUNTIME_ENV", "production")
        monkeypatch.setenv("LIMA_RATE_LIMIT_DISABLE", "1")
        from runtime_env import rate_limit_disabled

        assert rate_limit_disabled() is False


class TestCheckKeyLimit:
    def test_disabled_returns_none(self):
        with patch("routes.rate_limit_helper.rate_limit_disabled", return_value=True):
            assert check_key_limit("key", 10) is None

    def test_under_limit(self):
        with patch("routes.rate_limit_helper.rate_limit_disabled", return_value=False):
            with patch("routes.rate_limit_helper.rate_limiter.check_keyed_rate_limit", return_value=True):
                assert check_key_limit("key", 10) is None

    def test_over_limit(self):
        with patch("routes.rate_limit_helper.rate_limit_disabled", return_value=False):
            with patch("routes.rate_limit_helper.rate_limiter.check_keyed_rate_limit", return_value=False):
                response = check_key_limit("key", 10)
                assert response.status_code == 429
                assert "rate_limit_error" in response.body.decode()
