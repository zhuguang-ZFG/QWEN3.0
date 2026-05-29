"""Tests for Telegram /news /hot /tools commands."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

pytestmark = pytest.mark.asyncio


async def test_cmd_hot_sends_formatted_text(monkeypatch):
    import routes.telegram_public_tools as mod

    sent: list[str] = []

    async def fake_send(text, **kwargs):
        sent.append(text)

    monkeypatch.setattr(mod.telegram_bot, "send_message", fake_send)
    from channel_gateway import public_apis

    monkeypatch.setattr(
        public_apis,
        "fetch_hot_60s",
        lambda platform: {"ok": True, "text": f"hot:{platform}"},
    )

    await mod.cmd_hot("chat-1", "百度")
    assert sent and "hot:百度" in sent[0]


async def test_cmd_news_uses_60s_when_no_args(monkeypatch):
    import routes.telegram_public_tools as mod

    sent: list[str] = []

    async def fake_send(text, **kwargs):
        sent.append(text)

    monkeypatch.setattr(mod.telegram_bot, "send_message", fake_send)
    monkeypatch.setattr(
        mod,
        "_run_tool",
        lambda tool, args: {"ok": True, "text": "briefing"},
    )

    await mod.cmd_news("chat-1", "")
    assert sent == ["briefing"]


async def test_cmd_public_tool_weather(monkeypatch):
    import routes.telegram_public_tools as mod

    sent: list[str] = []

    async def fake_send(text, **kwargs):
        sent.append(text)

    monkeypatch.setattr(mod.telegram_bot, "send_message", fake_send)
    monkeypatch.setattr(
        mod,
        "_run_tool",
        lambda tool, args: {"ok": True, "text": f"{tool}:{args}"},
    )

    await mod.cmd_public_tool("chat-1", "weather", "北京")
    assert sent == ["weather:北京"]
