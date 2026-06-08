"""Notification module: Telegram alerts for newly discovered providers."""

import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("LIMA_TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("LIMA_TELEGRAM_CHAT_ID", "")


async def send_telegram(message: str) -> bool:
    """Send a Telegram notification via bot API."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.info("Telegram not configured, skipping notification")
        return False

    try:
        import httpx

        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                url,
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": message,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
            )
            if resp.status_code == 200:
                logger.info("Telegram notification sent")
                return True
            logger.debug("Telegram send failed: HTTP %d", resp.status_code)
            return False
    except Exception as exc:
        logger.warning("Telegram notification error: %s", type(exc).__name__)
        return False


def format_discovery_summary(summary: dict) -> str:
    """Format a discovery summary into a readable Telegram message.

    Args:
        summary: Output from discovery.scheduler.run_all_discovery()

    Returns:
        HTML-formatted message string.
    """
    new_count = summary.get("new_count", 0)
    total = summary.get("total_known", 0)
    sources = summary.get("sources", {})

    lines = [
        "<b> LiMa Provider Discovery Report</b>",
        f"<i>{datetime.now().strftime('%Y-%m-%d %H:%M UTC')}</i>",
        "",
        f" New providers found: <b>{new_count}</b>",
        f" Total known: <b>{total}</b>",
        "",
        "<b>Sources scanned:</b>",
    ]

    for source, result in sources.items():
        if isinstance(result, int):
            lines.append(f"  {source}: {result} found")
        else:
            lines.append(f"  {source}: {result}")

    # List new providers
    new_providers = summary.get("new_providers", [])
    if new_providers:
        lines.append("")
        lines.append("<b> New providers:</b>")
        for p in new_providers[:10]:
            name = p.get("name", p.get("url", "?"))[:60]
            src = p.get("source", "?")
            free = " FREE" if p.get("is_free") else ""
            lines.append(f"  [{src}] {name}{free}")

    if len(new_providers) > 10:
        lines.append(f"  ... and {len(new_providers) - 10} more")

    return "\n".join(lines)


async def notify_discovery(summary: dict) -> bool:
    """Send discovery results via Telegram.

    Only sends if new providers were found.
    """
    new_count = summary.get("new_count", 0)
    if new_count == 0:
        logger.info("No new providers, skipping notification")
        return True

    message = format_discovery_summary(summary)
    return await send_telegram(message)


async def notify_new_provider(provider: dict) -> bool:
    """Send a notification about a single newly verified provider."""
    name = provider.get("name", provider.get("url", "unknown"))
    url = provider.get("url", "")
    is_free = provider.get("is_free", False)
    coding_score = provider.get("coding_score", -1)

    lines = [
        "<b> New Provider Discovered!</b>",
        "",
        f"<b>Name:</b> {name}",
        f"<b>URL:</b> {url}",
        f"<b>Free:</b> {'Yes ' if is_free else 'No'}",
    ]

    if coding_score >= 0:
        lines.append(f"<b>Coding Score:</b> {coding_score}/5")

    lines.append("")
    lines.append("<i>Auto-discovered by LiMa Provider Probe</i>")

    return await send_telegram("\n".join(lines))
