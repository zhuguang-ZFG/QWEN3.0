"""Tests for Telegram /evalslice operator command."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

pytestmark = pytest.mark.asyncio


async def test_cmd_evalslice_reports_success(monkeypatch):
    import routes.telegram_eval_tools as mod

    sent: list[str] = []

    async def fake_send(text, **kwargs):
        sent.append(text)

    monkeypatch.setattr(mod.telegram_bot, "send_message", fake_send)
    monkeypatch.setattr(mod, "_run_eval_slice", lambda quick=True: 0)

    await mod.cmd_evalslice("chat-1", "")
    assert any("完成" in s for s in sent)


async def test_cmd_evalslice_full_mode(monkeypatch):
    import routes.telegram_eval_tools as mod

    calls: list[bool] = []

    def fake_run(*, quick=True):
        calls.append(quick)
        return 0

    async def fake_send(text, **kwargs):
        return None

    monkeypatch.setattr(mod.telegram_bot, "send_message", fake_send)
    monkeypatch.setattr(mod, "_run_eval_slice", fake_run)

    await mod.cmd_evalslice("chat-1", "full")
    assert calls == [False]
