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


async def test_cmd_evalreport_shows_summary(monkeypatch):
    import routes.telegram_eval_tools as mod
    from pathlib import Path

    sent: list[str] = []

    async def fake_send(text, **kwargs):
        sent.append(text)

    monkeypatch.setattr(mod.telegram_bot, "send_message", fake_send)
    monkeypatch.setattr(
        mod,
        "latest_scores_path",
        lambda data_dir, full=False: Path("data/coding_backend_scores.json"),
    )
    monkeypatch.setattr(mod, "summarize_eval_json", lambda path, top_n=5: "Eval 摘要 test")

    await mod.cmd_evalreport("chat-1", "")
    assert sent and "Eval 摘要 test" in sent[-1]


async def test_cmd_archiveeval_writes_archive(monkeypatch):
    import routes.telegram_eval_tools as mod
    from pathlib import Path

    sent: list[str] = []

    async def fake_send(text, **kwargs):
        sent.append(text)

    monkeypatch.setattr(mod.telegram_bot, "send_message", fake_send)
    monkeypatch.setattr(
        mod,
        "latest_scores_path",
        lambda data_dir, full=False: Path("data/coding_backend_scores_full.json"),
    )
    monkeypatch.setattr(
        mod,
        "summarize_eval_json",
        lambda path, top_n=5: "Eval 摘要 archive",
    )

    await mod.cmd_archiveeval("chat-1", "full")
    assert any("[TG-ARCHIVE]" in s for s in sent)
    assert any("冷存储" in s for s in sent)
