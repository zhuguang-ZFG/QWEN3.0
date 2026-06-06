"""Telegram operator tools — backend / proxy diagnosis."""

from __future__ import annotations

import asyncio
import logging

import telegram_bot
from notify.ops_alerts import maybe_notify_oldllm_failure
from oldllm_diag import REFRESH_HINTS, failure_hints, run_diag
from oldllm_sync import format_sync_result, try_sync
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
        if item.get("skipped"):
            reason = item.get("skip_reason", "不在本机")
            lines.append(f"[SKIP] {label}/{kind} — {reason}")
            continue
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
    hints = report.get("hints") or failure_hints(report)
    if hints:
        lines.append("")
        lines.append("修复建议:")
        for hint in hints[:5]:
            lines.append(f"· {hint}")
    return "\n".join(lines)


async def cmd_oldllm(chat_id: str, args: str) -> None:
    mode = args.strip().lower()
    if mode in ("sync", "s") or mode.startswith("sync "):
        await _cmd_oldllm_sync(chat_id, mode)
        return

    models_only = mode in ("models", "m", "list")
    show_refresh = mode in ("refresh", "fix", "r") or "refresh" in mode.split()
    label = "OldLLM 刷新诊断" if show_refresh else "OldLLM 探针"
    await telegram_bot.send_message(f"{label}运行中…", chat_id=chat_id)
    try:
        kwargs: dict = {"skip_chat": models_only}
        if show_refresh:
            kwargs["chat_timeout"] = 45.0
        report = await asyncio.to_thread(run_diag, **kwargs)
        text = _format_oldllm_report(report)
        if show_refresh and not report.get("upstream_chat_ok", report.get("any_chat_ok")):
            shown = set(report.get("hints") or [])
            win_lines = [h for h in REFRESH_HINTS if h not in shown]
            if win_lines:
                text += "\n\nWindows 操作:\n" + "\n".join(f"· {h}" for h in win_lines)
            await asyncio.to_thread(maybe_notify_oldllm_failure, report)
        await telegram_bot.send_message(text, chat_id=chat_id)
    except Exception as exc:
        _log.exception("cmd_oldllm failed")
        await telegram_bot.send_message(_operator_error("oldllm"), chat_id=chat_id)


async def _cmd_oldllm_sync(chat_id: str, mode: str) -> None:
    capture = "capture" in mode.split()
    await telegram_bot.send_message("OldLLM sync 运行中…", chat_id=chat_id)
    try:
        sync_result = await asyncio.to_thread(try_sync, capture=capture)
        report = await asyncio.to_thread(run_diag, chat_timeout=45.0)
        parts = [format_sync_result(sync_result), "", _format_oldllm_report(report)]
        if not report.get("upstream_chat_ok", report.get("any_chat_ok")):
            await asyncio.to_thread(maybe_notify_oldllm_failure, report)
        await telegram_bot.send_message("\n".join(parts), chat_id=chat_id)
    except Exception as exc:
        _log.exception("cmd_oldllm sync failed")
        await telegram_bot.send_message(_operator_error("oldllm sync"), chat_id=chat_id)
