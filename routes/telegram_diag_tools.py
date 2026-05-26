"""Telegram operator tools — backend / proxy diagnosis."""

from __future__ import annotations

import asyncio
import logging

import telegram_bot
from oldllm_diag import run_diag
from routes.telegram_commands import _operator_error

_log = logging.getLogger(__name__)


def _format_oldllm_report(report: dict) -> str:
    lines = [
        "TheOldLLM 诊断",
        f"upstream: {report.get('upstream', '?')}",
        f"local: {report.get('local_proxy', '?')}",
    ]
    for item in report.get("results", []):
        label = item.get("label", "?")
        kind = item.get("kind", "?")
        ok = item.get("ok")
        mark = "ok" if ok else "FAIL"
        status = item.get("status")
        elapsed = item.get("elapsed_sec")
        extra = ""
        if kind == "models":
            extra = f" n={item.get('model_count', 0)}"
        elif kind == "chat":
            if item.get("timed_out"):
                extra = " timeout"
        lines.append(f"[{mark}] {label}/{kind} {status} {elapsed}s{extra}")
    lines.append(
        f"summary models={report.get('any_models_ok')} chat={report.get('any_chat_ok')}"
    )
    return "\n".join(lines)


async def cmd_oldllm(chat_id: str, args: str) -> None:
    mode = args.strip().lower()
    models_only = mode in ("models", "m", "list")
    await telegram_bot.send_message("OldLLM 探针运行中…", chat_id=chat_id)
    try:
        report = await asyncio.to_thread(
            run_diag,
            skip_chat=models_only,
        )
        await telegram_bot.send_message(_format_oldllm_report(report), chat_id=chat_id)
    except Exception:
        _log.exception("cmd_oldllm failed")
        await telegram_bot.send_message(_operator_error("oldllm"), chat_id=chat_id)
