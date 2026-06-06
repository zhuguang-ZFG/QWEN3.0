"""Tests for Telegram /evalslice operator command."""

import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

pytestmark = pytest.mark.asyncio


async def _run_evalslice_tasks(mod, monkeypatch):
    """Run background eval tasks inline for deterministic tests."""
    created: list[asyncio.Task] = []

    def _capture(task):
        created.append(task)

    monkeypatch.setattr(mod.asyncio, "create_task", _capture)
    return created


async def test_cmd_evalslice_reports_success(monkeypatch):
    import routes.telegram_eval_tools as mod

    sent: list[str] = []

    async def fake_send(text, **kwargs):
        sent.append(text)

    async def fake_send_kb(text, keyboard=None, **kwargs):
        sent.append(text)
        return 42  # mock message_id

    async def fake_edit(text, message_id, **kwargs):
        sent.append(text)
        return True

    monkeypatch.setattr(mod.telegram_bot, "send_message", fake_send)
    monkeypatch.setattr(mod.telegram_bot, "send_message_with_keyboard", fake_send_kb)
    monkeypatch.setattr(mod.telegram_bot, "edit_message_text", fake_edit)
    monkeypatch.setattr(mod, "_run_eval_slice", lambda quick=True: (0, "eval_preflight_ok health ok"))

    created = await _run_evalslice_tasks(mod, monkeypatch)
    await mod.cmd_evalslice("chat-1", "")
    assert created
    await created[0]

    assert any("Eval" in s for s in sent)


async def test_cmd_evalslice_busy_guard(monkeypatch):
    import routes.telegram_eval_tools as mod

    mod._eval_busy = True
    sent: list[str] = []

    async def fake_send(text, **kwargs):
        sent.append(text)

    monkeypatch.setattr(mod.telegram_bot, "send_message", fake_send)
    await mod.cmd_evalslice("chat-1", "full")
    mod._eval_busy = False
    assert any("已有 Eval 运行中" in s for s in sent)


async def test_cmd_evalslice_full_mode(monkeypatch):
    import routes.telegram_eval_tools as mod

    calls: list[bool] = []

    def fake_run(*, quick=True):
        calls.append(quick)
        return 0, "ok"

    async def fake_send(text, **kwargs):
        return None

    monkeypatch.setattr(mod.telegram_bot, "send_message", fake_send)
    monkeypatch.setattr(mod, "_run_eval_slice", fake_run)

    created = await _run_evalslice_tasks(mod, monkeypatch)
    await mod.cmd_evalslice("chat-1", "full")
    await created[0]
    assert calls == [False]


async def test_cmd_evalreport_shows_summary(monkeypatch):
    from pathlib import Path

    import routes.telegram_eval_tools as mod

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
    from pathlib import Path

    import routes.telegram_eval_tools as mod

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


async def test_cmd_evalschedule_shows_lines(monkeypatch):
    import routes.telegram_eval_tools as mod

    sent: list[str] = []

    async def fake_send(text, **kwargs):
        sent.append(text)

    monkeypatch.setattr(mod.telegram_bot, "send_message", fake_send)
    await mod.cmd_evalschedule("chat-1", "")
    assert sent and "LIMA_PERIODIC_CODING_EVAL" in sent[-1]


async def test_cmd_evalstatus(monkeypatch):
    import routes.telegram_eval_tools as mod

    sent: list[str] = []

    async def fake_send(text, **kwargs):
        sent.append(text)

    monkeypatch.setattr(mod.telegram_bot, "send_message", fake_send)
    monkeypatch.setattr(
        "eval_status.build_eval_status",
        lambda data_dir, eval_busy=False: "Eval 运维总览 test",
    )
    await mod.cmd_evalstatus("chat-1", "")
    assert sent and "Eval 运维总览 test" in sent[-1]


async def test_cmd_evaldigest(monkeypatch):
    import routes.telegram_eval_tools as mod

    sent: list[str] = []

    async def fake_send(text, **kwargs):
        sent.append(text)

    monkeypatch.setattr(mod.telegram_bot, "send_message", fake_send)
    monkeypatch.setattr(
        "eval_digest.build_eval_digest",
        lambda data_dir: "Eval 合并摘要 test",
    )
    await mod.cmd_evaldigest("chat-1", "")
    assert sent and "Eval 合并摘要 test" in sent[-1]


async def test_cmd_archiveeval_document_upload(monkeypatch):
    from pathlib import Path

    import routes.telegram_eval_tools as mod

    sent: list[str] = []
    docs: list[Path] = []

    async def fake_send(text, **kwargs):
        sent.append(text)

    async def fake_doc(path, **kwargs):
        docs.append(Path(path))
        return True

    monkeypatch.setattr(mod.telegram_bot, "send_message", fake_send)
    monkeypatch.setattr(mod.telegram_bot, "send_document", fake_doc)
    fake_path = Path("data/coding_backend_scores_full.json")
    monkeypatch.setattr(
        mod,
        "latest_scores_path",
        lambda data_dir, full=False: fake_path,
    )
    monkeypatch.setattr(
        mod,
        "summarize_eval_json",
        lambda path, top_n=5: "Eval 摘要 archive",
    )

    await mod.cmd_archiveeval("chat-1", "full doc")
    assert docs == [fake_path]
    assert any("document ok" in s for s in sent)
