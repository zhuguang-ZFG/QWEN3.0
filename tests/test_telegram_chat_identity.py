"""Telegram chat identity intercept tests."""

from unittest.mock import AsyncMock, patch

import pytest

import identity_guard
from routes.telegram_chat_identity import maybe_identity_answer, sanitize_chat_answer


def test_ni_shi_shen_me_matches_identity_guard():
    assert identity_guard.detect_identity_question("你是什么") is not None
    assert identity_guard.detect_identity_question("你是什么模型") is not None


def test_sanitize_chat_answer_strips_llama_leak():
    leaked = (
        "我是Meta AI的一个版本，特别是他们的LLaMA（大型语言模型应用）模型。"
        "我的模型有数十亿个参数。"
    )
    out = sanitize_chat_answer("你是什么模型", leaked)
    assert "LLaMA" not in out
    assert "Meta" not in out or "LiMa" in out


@pytest.mark.asyncio
async def test_cmd_chat_short_circuits_identity_before_stream(monkeypatch):
    monkeypatch.setenv("TELEGRAM_STREAM_CHAT", "1")
    send = AsyncMock(return_value=True)
    monkeypatch.setattr("telegram_bot.send_message", send)
    stream_called = {"n": 0}

    async def fake_stream(*_a, **_k):
        stream_called["n"] += 1
        return "should not run"

    monkeypatch.setattr(
        "routes.telegram_chat_stream.stream_chat_to_telegram",
        fake_stream,
    )

    from routes import telegram_commands

    telegram_commands._chat_histories.clear()
    await telegram_commands.cmd_chat("chat-id", "你是什么模型")

    send.assert_awaited_once()
    body = send.await_args.args[0]
    assert "LiMa" in body
    assert "力码" in body
    assert stream_called["n"] == 0


@pytest.mark.asyncio
async def test_stream_chat_returns_identity_without_speculative(monkeypatch):
    monkeypatch.setenv("TELEGRAM_STREAM_CHAT", "1")
    send = AsyncMock(return_value=True)
    monkeypatch.setattr("telegram_bot.send_message", send)

    async def fail_stream(*_a, **_k):
        raise AssertionError("speculative_stream_chunks should not run")

    monkeypatch.setattr(
        "routes.telegram_chat_stream.speculative_stream_chunks",
        fail_stream,
    )

    from routes.telegram_chat_stream import stream_chat_to_telegram

    out = await stream_chat_to_telegram("123", "你是什么", [])
    assert "LiMa" in out
    send.assert_awaited()
