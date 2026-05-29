"""Tests for Telegram inline query handler (TG-10.0-3)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

import telegram_inline


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    telegram_inline.reset_inline_rate_limit_for_tests()
    yield
    telegram_inline.reset_inline_rate_limit_for_tests()


class TestInlineHelpers:
    def test_build_inline_results_article_shape(self):
        results = telegram_inline.build_inline_results("fib", "1,1,2,3")
        assert len(results) == 1
        item = results[0]
        assert item["type"] == "article"
        assert item["title"] == "fib"
        assert "1,1,2,3" in item["input_message_content"]["message_text"]

    def test_route_inline_query_empty_hint(self, monkeypatch):
        monkeypatch.setattr(telegram_inline.routing_engine, "route", lambda **_: {"answer": "x"})
        assert "请输入" in telegram_inline.route_inline_query("  ")

    def test_route_inline_query_calls_engine(self, monkeypatch):
        seen = {}

        def fake_route(**kwargs):
            seen.update(kwargs)
            return {"answer": "ok"}

        monkeypatch.setattr(telegram_inline.routing_engine, "route", fake_route)
        assert telegram_inline.route_inline_query("hello") == "ok"
        assert seen["query"] == "hello"


class TestHandleInlineQuery:
    @pytest.mark.asyncio
    async def test_disabled_returns_false(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_INLINE_ENABLED", "0")
        ok = await telegram_inline.handle_inline_query({"id": "q1", "from": {"id": 1}, "query": "hi"})
        assert ok is False

    @pytest.mark.asyncio
    async def test_unauthorized_empty_results(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_INLINE_ENABLED", "1")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "999")
        answer = AsyncMock(return_value=True)
        with patch.object(telegram_inline.telegram_bot, "answer_inline_query", answer):
            ok = await telegram_inline.handle_inline_query(
                {"id": "q1", "from": {"id": 111}, "query": "hi"}
            )
        assert ok is True
        answer.assert_awaited_once_with("q1", [], cache_time=5)

    @pytest.mark.asyncio
    async def test_authorized_routes_and_answers(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_INLINE_ENABLED", "1")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "111")
        monkeypatch.setattr(telegram_inline, "route_inline_query", lambda q: f"ans:{q}")
        answer = AsyncMock(return_value=True)
        with patch.object(telegram_inline.telegram_bot, "answer_inline_query", answer):
            ok = await telegram_inline.handle_inline_query(
                {"id": "q2", "from": {"id": 111}, "query": "fib"}
            )
        assert ok is True
        args, kwargs = answer.await_args
        assert args[0] == "q2"
        assert args[1][0]["type"] == "article"
        assert "ans:fib" in args[1][0]["input_message_content"]["message_text"]
