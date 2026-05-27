"""Telegram bridge for developer skills: /investigate, /review, /ship."""

from __future__ import annotations

import logging

import telegram_bot

_log = logging.getLogger(__name__)


async def cmd_investigate(chat_id: str, args: str) -> None:
    """Handle /investigate <file-or-query> from Telegram."""
    target = args.strip()
    if not target:
        await telegram_bot.send_message(
            "Usage: `/investigate <file.py>` or `/investigate <error description>`",
            chat_id=chat_id, parse_mode="Markdown",
        )
        return

    await telegram_bot.send_message(f"Investigating: `{target}`...", chat_id=chat_id, parse_mode="Markdown")

    try:
        from developer_skills.investigate import investigate
        result = investigate(target)
        parts = [f"**Investigation: {target}**\n"]
        for detail in result.details[:15]:
            parts.append(detail)
        if result.evidence:
            parts.append(f"\n_Evidence: {', '.join(result.evidence[:5])}_")
        await telegram_bot.send_message(
            "\n".join(parts)[:3000], chat_id=chat_id, parse_mode="Markdown",
        )
    except Exception as exc:
        _log.warning("investigate failed: %s", exc)
        await telegram_bot.send_message(
            f"Investigation failed: {type(exc).__name__}",
            chat_id=chat_id,
        )


async def cmd_review(chat_id: str, args: str) -> None:
    """Handle /review <file-or-dir> from Telegram."""
    target = args.strip()
    if not target:
        await telegram_bot.send_message(
            "Usage: `/review <file.py>` or `/review <directory/>`",
            chat_id=chat_id, parse_mode="Markdown",
        )
        return

    await telegram_bot.send_message(f"Reviewing: `{target}`...", chat_id=chat_id, parse_mode="Markdown")

    try:
        from developer_skills.review import review
        result = review(target)
        parts = [f"**Review: {result.summary}**\n"]
        for detail in result.details[:20]:
            parts.append(detail)
        if result.evidence:
            parts.append(f"\n_Evidence: {', '.join(result.evidence[:5])}_")
        await telegram_bot.send_message(
            "\n".join(parts)[:3000], chat_id=chat_id, parse_mode="Markdown",
        )
    except Exception as exc:
        _log.warning("review failed: %s", exc)
        await telegram_bot.send_message(
            f"Review failed: {type(exc).__name__}",
            chat_id=chat_id,
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
