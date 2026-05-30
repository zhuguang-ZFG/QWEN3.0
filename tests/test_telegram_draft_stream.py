"""Tests for Telegram sendMessageDraft streaming (TG-10.0-1)."""

import os

import pytest

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("TELEGRAM_CHAT_ID", "987654321")

import telegram_draft_stream
import routes.telegram_commands as telegram_commands


class TestTelegramDraftStream:
    def test_stream_chat_enabled_default_on(self, monkeypatch):
        monkeypatch.delenv("TELEGRAM_STREAM_CHAT", raising=False)
        assert telegram_draft_stream.stream_chat_enabled() is True

    def test_stream_chat_disabled(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_STREAM_CHAT", "0")
        assert telegram_draft_stream.stream_chat_enabled() is False

    @pytest.mark.asyncio
    async def test_draft_streamer_throttles_updates(self, monkeypatch):
        calls: list[str] = []

        async def fake_api(method, data):
            calls.append(data["text"])
            return {"ok": True}

        monkeypatch.setattr(telegram_draft_stream.telegram_bot, "_api_call", fake_api)
        monkeypatch.setenv("TELEGRAM_STREAM_THROTTLE_MS", "5000")

        streamer = telegram_draft_stream.TelegramDraftStreamer("123")
        await streamer.start()
        await streamer.push("hello")
        await streamer.push("hello world")
        assert calls == ["", "hello"]

        await streamer.push("hello world", force=True)
        assert calls[-1] == "hello world"

    @pytest.mark.asyncio
    async def test_draft_streamer_finalize_sends_message(self, monkeypatch):
        sent: list[str] = []

        async def fake_api(method, data):
            return {"ok": True}

        async def fake_send(text, chat_id="", parse_mode="Markdown"):
            sent.append(text)
            return True

        monkeypatch.setattr(telegram_draft_stream.telegram_bot, "_api_call", fake_api)
        monkeypatch.setattr(telegram_draft_stream.telegram_bot, "send_message", fake_send)

        streamer = telegram_draft_stream.TelegramDraftStreamer("123")
        ok = await streamer.finalize("final answer")
        assert ok is True
        assert sent == ["final answer"]

    @pytest.mark.asyncio
    async def test_cmd_chat_uses_stream_when_enabled(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_STREAM_CHAT", "1")
        monkeypatch.setattr(telegram_commands, "_optional_import", lambda _name: None)

        async def fake_stream(chat_id, query, messages, **kwargs):
            return "streamed answer"

        monkeypatch.setattr(
            "routes.telegram_chat_stream.stream_chat_to_telegram",
            fake_stream,
        )

        await telegram_commands.cmd_chat("chat-1", "explain asyncio briefly")
        history = telegram_commands._get_history("chat-1")
        assert history[-1]["content"] == "streamed answer"

    @pytest.mark.asyncio
    async def test_cmd_chat_falls_back_when_fc_caller_is_unavailable(self, monkeypatch):
        sent = []

        async def fake_send_message(text, chat_id=None, **_kwargs):
            sent.append((text, chat_id))
            return True

        monkeypatch.setenv("TELEGRAM_STREAM_CHAT", "0")
        monkeypatch.setattr(telegram_commands, "_optional_import", lambda _name: None)
        monkeypatch.setattr(telegram_commands.telegram_bot, "send_message", fake_send_message)
        monkeypatch.setattr(
            telegram_commands.routing_engine,
            "route",
            lambda **_kwargs: {"answer": "fallback answer"},
        )

        await telegram_commands.cmd_chat("chat-1", "天气怎么样")

        assert sent[-1] == ("fallback answer", "chat-1")
