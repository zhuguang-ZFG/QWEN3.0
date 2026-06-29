"""Tests for backends_registry/_utils.py — registry helpers."""

from backends_registry._utils import legacy_free_enabled


class TestLegacyFreeEnabled:
    def test_default_disabled(self, monkeypatch):
        monkeypatch.delenv("LIMA_FREE_TEST_ENABLED", raising=False)
        monkeypatch.delenv("FREE_TEST_ENABLED", raising=False)
        assert legacy_free_enabled("test") is False

    def test_lima_prefixed_flag(self, monkeypatch):
        monkeypatch.delenv("FREE_TEST_ENABLED", raising=False)
        monkeypatch.setenv("LIMA_FREE_TEST_ENABLED", "1")
        assert legacy_free_enabled("test") is True

    def test_legacy_flag_warns(self, monkeypatch):
        monkeypatch.delenv("LIMA_FREE_TEST_ENABLED", raising=False)
        monkeypatch.setenv("FREE_TEST_ENABLED", "1")
        assert legacy_free_enabled("test") is True

    def test_lima_takes_precedence(self, monkeypatch):
        monkeypatch.setenv("LIMA_FREE_TEST_ENABLED", "0")
        monkeypatch.setenv("FREE_TEST_ENABLED", "1")
        assert legacy_free_enabled("test") is False
