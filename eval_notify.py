"""Telegram notifications after coding eval runs (periodic or manual hook)."""

from __future__ import annotations

import asyncio
import logging
import os
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent


def periodic_notify_enabled() -> bool:
    default = "1" if os.environ.get("LIMA_PERIODIC_CODING_EVAL", "0").strip().lower() in {
        "1",
        "true",
        "yes",
    } else "0"
    return os.environ.get("LIMA_PERIODIC_EVAL_NOTIFY_TG", default).strip().lower() in {
        "1",
        "true",
        "yes",
    }


def periodic_full_eval() -> bool:
    return os.environ.get("LIMA_PERIODIC_CODING_EVAL_FULL", "0").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _build_message(*, code: int, quick: bool, source: str) -> str:
    from eval_slice_summary import latest_scores_path, summarize_eval_json

    label = "quick" if quick else "full-11"
    lines = [f"[Eval] {source} {label} exit={code}"]
    if code != 0:
        return "\n".join(lines)

    path = latest_scores_path(ROOT / "data", full=not quick)
    if path:
        try:
            top = 5 if quick else 11
            lines.append(summarize_eval_json(path, top_n=top))
        except Exception:
            logger.warning("eval notify summary failed", exc_info=True)

    try:
        from eval_pool_gate import demoted_backends, load_eval_averages, pool_gate_enabled

        if pool_gate_enabled():
            blocked = sorted(demoted_backends(ROOT / "data"))
            scores = load_eval_averages(ROOT / "data")
            lines.append(f"pool gate demoted={len(blocked)}")
            for name in blocked[:5]:
                lines.append(f"· {name}: avg={scores.get(name, 0):.0f}")
    except Exception:
        logger.debug("pool gate summary skipped", exc_info=True)

    return "\n".join(lines)


async def _send_eval_telegram(text: str) -> None:
    import telegram_bot

    if not telegram_bot.is_configured():
        return
    await telegram_bot.send_message(text[:4000], parse_mode="")


async def _maybe_auto_archive(*, quick: bool) -> None:
    if os.environ.get("LIMA_EVAL_AUTO_ARCHIVE_TG", "0").strip().lower() not in {
        "1",
        "true",
        "yes",
    }:
        return
    import telegram_bot
    from eval_slice_summary import latest_scores_path, summarize_eval_json
    from telegram_archive import chunk_text, format_archive_message

    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not chat_id or not telegram_bot.is_configured():
        return
    path = latest_scores_path(ROOT / "data", full=not quick)
    if not path:
        return
    top = 11 if not quick else 5
    body = summarize_eval_json(path, top_n=top)
    label = f"eval-{'full' if not quick else 'quick'}:{path.name}"
    message = format_archive_message(label, body)
    parts = chunk_text(message)
    for idx, part in enumerate(parts, start=1):
        prefix = f"({idx}/{len(parts)})\n" if len(parts) > 1 else ""
        await telegram_bot.send_message(prefix + part, chat_id=chat_id, parse_mode="")
    if not quick:
        await telegram_bot.send_document(
            path,
            chat_id=chat_id,
            caption=f"[TG-ARCHIVE] {label}",
            filename=path.name,
        )


def notify_eval_finished(*, code: int, quick: bool, source: str = "periodic") -> None:
    """Fire-and-forget Telegram summary (+ optional TG archive)."""
    if source == "periodic" and not periodic_notify_enabled():
        return

    text = _build_message(code=code, quick=quick, source=source)

    def _runner() -> None:
        try:
            asyncio.run(_send_eval_telegram(text))
            if code == 0:
                asyncio.run(_maybe_auto_archive(quick=quick))
        except Exception:
            logger.exception("eval notify failed source=%s", source)

    threading.Thread(target=_runner, name="eval-notify-tg", daemon=True).start()


def schedule_status_lines() -> list[str]:
    import periodic_coding_eval

    lines = [
        "Eval 周期任务",
        f"LIMA_PERIODIC_CODING_EVAL={'1' if periodic_coding_eval.enabled() else '0'}",
        f"interval_hours={os.environ.get('LIMA_CODING_EVAL_INTERVAL_HOURS', '168')}",
        f"full={'1' if periodic_full_eval() else '0'} (quick only if 0)",
        f"notify_tg={'1' if periodic_notify_enabled() else '0'}",
        f"auto_archive_tg={os.environ.get('LIMA_EVAL_AUTO_ARCHIVE_TG', '0')}",
    ]
    return lines
