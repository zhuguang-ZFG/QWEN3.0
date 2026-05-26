"""Tests for Telegram /oldllm diagnosis command."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

import routes.telegram_diag_tools as mod


@pytest.mark.asyncio
async def test_cmd_oldllm_reports(monkeypatch):
    sent: list[str] = []
    monkeypatch.setattr(
        mod.telegram_bot,
        "send_message",
        AsyncMock(side_effect=lambda text, chat_id=None: sent.append(text)),
    )
    monkeypatch.setattr(
        mod,
        "run_diag",
        lambda **kwargs: {
            "upstream": "https://up.test",
            "local_proxy": "http://127.0.0.1:4502",
            "any_models_ok": True,
            "any_chat_ok": False,
            "results": [
                {
                    "label": "upstream",
                    "kind": "models",
                    "ok": True,
                    "status": 200,
                    "elapsed_sec": 0.1,
                    "model_count": 2,
                },
                {
                    "label": "upstream",
                    "kind": "chat",
                    "ok": False,
                    "status": 502,
                    "elapsed_sec": 0.3,
                    "timed_out": False,
                },
            ],
        },
    )

    await mod.cmd_oldllm("chat-1", "")

    assert len(sent) == 2
    assert "TheOldLLM" in sent[1]
    assert "502" in sent[1]


@pytest.mark.asyncio
async def test_cmd_oldllm_models_only(monkeypatch):
    captured: dict = {}

    def _fake_run(**kwargs):
        captured.update(kwargs)
        return {
            "upstream": "u",
            "local_proxy": "l",
            "any_models_ok": True,
            "any_chat_ok": False,
            "results": [],
        }

    monkeypatch.setattr(mod.telegram_bot, "send_message", AsyncMock())
    monkeypatch.setattr(mod, "run_diag", _fake_run)

    await mod.cmd_oldllm("chat-1", "models")

    assert captured.get("skip_chat") is True
