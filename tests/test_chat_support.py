"""Tests for routes/chat_support.py — chat support helpers."""

from unittest.mock import patch

from routes.chat_support import _get_thinking_backend


class TestGetThinkingBackend:
    def test_prefers_available_thinking_backend(self):
        backends = {
            "openai_thinking": {"key": "sk-123"},
        }
        with patch("routes.chat_support.BACKENDS", backends):
            with patch("routes.chat_support.THINKING_BACKENDS", ["openai_thinking"]):
                with patch("routes.chat_support.health_tracker.is_cooled_down", return_value=False):
                    assert _get_thinking_backend() == "openai_thinking"

    def test_fallback_when_none_available(self):
        with patch("routes.chat_support.BACKENDS", {}):
            with patch("routes.chat_support.THINKING_BACKENDS", ["missing"]):
                assert _get_thinking_backend() == "longcat_thinking"

    def test_skips_cooled_down(self):
        backends = {
            "openai_thinking": {"key": "sk-123"},
            "longcat_thinking": {"key": ""},
        }
        with patch("routes.chat_support.BACKENDS", backends):
            with patch("routes.chat_support.THINKING_BACKENDS", ["openai_thinking", "longcat_thinking"]):
                with patch("routes.chat_support.health_tracker.is_cooled_down", return_value=True):
                    assert _get_thinking_backend() == "longcat_thinking"
