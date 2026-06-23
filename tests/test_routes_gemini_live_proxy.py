"""Tests for routes/gemini_live_proxy.py helpers."""

from __future__ import annotations

from routes.gemini_live_proxy import _google_api_key


class TestGoogleApiKey:
    def test_returns_key_when_set(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_AI_KEY", "gk_test_123")
        assert _google_api_key() == "gk_test_123"

    def test_returns_none_when_unset(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_AI_KEY", raising=False)
        assert _google_api_key() is None

    def test_returns_none_for_whitespace(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_AI_KEY", "   ")
        assert _google_api_key() is None
