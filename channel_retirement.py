"""Retired channel registry and startup cleanup helpers."""

from __future__ import annotations

import logging
import os
from collections.abc import MutableMapping

logger = logging.getLogger(__name__)

RETIRED_CHANNELS = frozenset({"telegram"})
RETIRED_ROUTE_PREFIXES = frozenset({"/telegram"})


def mark_retired_modules(loaded_modules: MutableMapping[str, bool]) -> None:
    """Expose retired channels as intentionally unavailable in health output."""
    for channel in RETIRED_CHANNELS:
        loaded_modules[channel] = False


def is_retired_route_path(path: str) -> bool:
    """Return whether a route path belongs to a retired channel."""
    return any(path.startswith(prefix) for prefix in RETIRED_ROUTE_PREFIXES)


def _telegram_bot_token() -> str:
    return (
        os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        or os.environ.get("LIMA_TELEGRAM_BOT_TOKEN", "").strip()
    )


async def retire_telegram_webhook_from_env() -> bool:
    """Best-effort Telegram webhook deregistration for legacy deployments."""
    if os.environ.get("PYTEST_CURRENT_TEST"):
        logger.info("telegram webhook cleanup skipped under pytest")
        return False

    token = _telegram_bot_token()
    if not token:
        logger.info("telegram webhook cleanup skipped: no legacy bot token configured")
        return False

    try:
        import httpx
    except ImportError:
        logger.warning("telegram webhook cleanup skipped: httpx unavailable")
        return False

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.post(
                f"https://api.telegram.org/bot{token}/deleteWebhook",
                json={"drop_pending_updates": True},
            )
    except Exception as exc:
        logger.warning("telegram webhook cleanup failed: %s", type(exc).__name__)
        return False

    if response.status_code >= 400:
        logger.warning("telegram webhook cleanup failed: http_status=%s", response.status_code)
        return False

    logger.info("telegram webhook cleanup completed for retired bot channel")
    return True
