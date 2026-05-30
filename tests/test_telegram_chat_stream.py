"""Tests for Telegram chat stream fallback."""

import pytest


@pytest.mark.asyncio
async def test_stream_falls_back_to_route_when_speculative_empty(monkeypatch):
    monkeypatch.setenv("TELEGRAM_STREAM_CHAT", "1")

    async def empty_stream(*_a, **_k):
        if False:
            yield
        return

    monkeypatch.setattr(
        "routes.telegram_chat_stream.speculative_stream_chunks",
        empty_stream,
    )
    monkeypatch.setattr(
        "routes.telegram_chat_stream._route_chat_sync",
        lambda q, m: "fallback answer from route",
    )

    class FakeStreamer:
        _stopped = False

        async def start(self):
            return None

        async def push(self, *_a, **_k):
            return None

        async def finalize(self, text):
            return True

    monkeypatch.setattr(
        "routes.telegram_chat_stream.TelegramDraftStreamer",
        lambda *_a, **_k: FakeStreamer(),
    )

    from routes.telegram_chat_stream import stream_chat_to_telegram

    out = await stream_chat_to_telegram("123", "hello", [])
    assert out == "fallback answer from route"
