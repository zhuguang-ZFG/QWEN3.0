"""Tests for Telegram codesearch operator command."""

import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

pytestmark = pytest.mark.asyncio


async def test_cmd_codesearch_status(monkeypatch):
    import routes.telegram_codesearch_tools as mod

    sent: list[str] = []

    async def fake_send(text, **kwargs):
        sent.append(text)

    monkeypatch.setattr(mod.telegram_bot, "send_message", fake_send)
    await mod.cmd_codesearch("chat-1", "")
    assert sent and "Codesearch MCP" in sent[0]


async def test_cmd_codesearch_search(monkeypatch):
    import routes.telegram_codesearch_tools as mod

    sent: list[str] = []

    async def fake_send(text, **kwargs):
        sent.append(text)

    monkeypatch.setattr(mod.telegram_bot, "send_message", fake_send)
    monkeypatch.setattr(
        mod,
        "probe_search",
        lambda q: {"ok": True, "query": q, "root": "/tmp", "results": [{"path": "a.py", "snippet": "x"}]},
    )
    await mod.cmd_codesearch("chat-1", "router")
    assert any("查询中" in s for s in sent)
    assert any("命中" in s for s in sent)
