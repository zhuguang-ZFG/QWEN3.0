"""Tests for backends_registry/_utils.py — registry helpers."""

from unittest.mock import patch

from backends_registry._utils import legacy_free_enabled


class TestLegacyFreeEnabled:
    def test_default_disabled(self):
        with patch.dict("os.environ", {}, clear=True):
            assert legacy_free_enabled("test") is False

    def test_lima_prefixed_flag(self):
        with patch.dict("os.environ", {"LIMA_FREE_TEST_ENABLED": "1"}):
            assert legacy_free_enabled("test") is True

    def test_legacy_flag_warns(self):
        with patch.dict("os.environ", {"FREE_TEST_ENABLED": "1"}):
            assert legacy_free_enabled("test") is True

    def test_lima_takes_precedence(self):
        with patch.dict("os.environ", {"LIMA_FREE_TEST_ENABLED": "0", "FREE_TEST_ENABLED": "1"}):
            assert legacy_free_enabled("test") is False
