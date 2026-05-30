"""Telegram bridge for developer skills: /investigate, /review, /ship."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

import telegram_bot

_log = logging.getLogger(__name__)


async def _run_target_skill(
    chat_id: str,
    args: str,
    *,
    usage: str,
    progress: str,
    load_runner: Callable[[], Callable[[str], Any]],
    format_header: Callable[[Any, str], str],
    detail_limit: int,
    failure_label: str,
) -> None:
    target = args.strip()
    if not target:
        await telegram_bot.send_message(
            usage,
            chat_id=chat_id, parse_mode="Markdown",
        )
        return

    await telegram_bot.send_message(f"{progress}: `{target}`...", chat_id=chat_id, parse_mode="Markdown")

    try:
        result = load_runner()(target)
        parts = [format_header(result, target)]
        for detail in result.details[:detail_limit]:
            parts.append(detail)
        if result.evidence:
            parts.append(f"\n_Evidence: {', '.join(result.evidence[:5])}_")
        await telegram_bot.send_message(
            "\n".join(parts)[:3000], chat_id=chat_id, parse_mode="Markdown",
        )
    except Exception as exc:
        _log.warning("%s failed: %s", failure_label.lower(), exc)
        await telegram_bot.send_message(
            f"{failure_label} failed: {type(exc).__name__}",
            chat_id=chat_id,
        )


async def cmd_investigate(chat_id: str, args: str) -> None:
    """Handle /investigate <file-or-query> from Telegram."""
    def load_runner() -> Callable[[str], Any]:
        from developer_skills.investigate import investigate

        return investigate

    await _run_target_skill(
        chat_id,
        args,
        usage="Usage: `/investigate <file.py>` or `/investigate <error description>`",
        progress="Investigating",
        load_runner=load_runner,
        format_header=lambda _result, target: f"**Investigation: {target}**\n",
        detail_limit=15,
        failure_label="Investigation",
    )


async def cmd_review(chat_id: str, args: str) -> None:
    """Handle /review <file-or-dir> from Telegram."""
    def load_runner() -> Callable[[str], Any]:
        from developer_skills.review import review

        return review

    await _run_target_skill(
        chat_id,
        args,
        usage="Usage: `/review <file.py>` or `/review <directory/>`",
        progress="Reviewing",
        load_runner=load_runner,
        format_header=lambda result, _target: f"**Review: {result.summary}**\n",
        detail_limit=20,
        failure_label="Review",
    )


async def cmd_ship(chat_id: str, args: str) -> None:
    """Handle /ship [message] from Telegram."""
    message = args.strip()

    try:
        from developer_skills.ship import ship
        result = ship(message, stage_all=True, push=True)
        parts = [f"**Ship: {result.summary}**\n"]
        for detail in result.details[:10]:
            parts.append(detail)
        if result.evidence:
            parts.append(f"\n_Evidence: {', '.join(result.evidence[:5])}_")
        await telegram_bot.send_message(
            "\n".join(parts)[:3000], chat_id=chat_id, parse_mode="Markdown",
        )
    except Exception as exc:
        _log.warning("ship failed: %s", exc)
        await telegram_bot.send_message(
            f"Ship failed: {type(exc).__name__}",
            chat_id=chat_id,
        )
