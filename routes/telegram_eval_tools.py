"""Telegram operator tools — coding eval slice trigger."""

from __future__ import annotations

import asyncio
import logging
import subprocess
import sys
from pathlib import Path

import telegram_bot
from eval_slice_summary import latest_scores_path, summarize_eval_json
from routes.telegram_commands import _operator_error

_log = logging.getLogger(__name__)
_ROOT = Path(__file__).resolve().parent.parent


def _run_eval_slice(*, quick: bool = True) -> int:
    cmd = [sys.executable, str(_ROOT / "scripts" / "run_radar_eval_slice.py"), "--preflight"]
    if quick:
        cmd.append("--quick")
    else:
        cmd.append("--full")
    return subprocess.call(cmd, cwd=_ROOT)


async def cmd_evalslice(chat_id: str, args: str) -> None:
    mode = args.strip().lower()
    quick = mode not in ("full", "all", "11")
    label = "quick" if quick else "full-11"
    hint = "（约 3 分钟）" if not quick else ""
    await telegram_bot.send_message(f"Eval slice ({label}) 启动中{hint}…", chat_id=chat_id)
    try:
        code = await asyncio.to_thread(_run_eval_slice, quick=quick)
        out = "coding_backend_scores_*.json" if quick else "coding_backend_scores_full_*.json"
        if code == 0:
            summary = ""
            path = latest_scores_path(_ROOT / "data", full=not quick)
            if path:
                try:
                    summary = "\n\n" + summarize_eval_json(path)
                except Exception:
                    _log.warning("eval slice summary failed path=%s", path, exc_info=True)
            await telegram_bot.send_message(
                f"Eval slice ({label}) 完成。见 data/{out}{summary}",
                chat_id=chat_id,
            )
        else:
            await telegram_bot.send_message(
                f"Eval slice ({label}) 失败 exit={code}",
                chat_id=chat_id,
            )
    except Exception:
        _log.exception("cmd_evalslice failed")
        await telegram_bot.send_message(_operator_error("evalslice"), chat_id=chat_id)


async def cmd_evalreport(chat_id: str, args: str) -> None:
    mode = args.strip().lower()
    full = mode in ("full", "all", "11")
    path = latest_scores_path(_ROOT / "data", full=full)
    if not path:
        label = "full-11" if full else "quick"
        await telegram_bot.send_message(
            f"尚无 {label} eval JSON（先跑 /evalslice{' full' if full else ''}）",
            chat_id=chat_id,
        )
        return
    try:
        text = summarize_eval_json(path)
        await telegram_bot.send_message(text, chat_id=chat_id)
    except Exception:
        _log.exception("cmd_evalreport failed")
        await telegram_bot.send_message(_operator_error("evalreport"), chat_id=chat_id)
