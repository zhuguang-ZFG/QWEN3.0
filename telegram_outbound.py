"""Telegram API outbound reachability checks (TG-GH-1)."""

from __future__ import annotations

import os
from typing import Callable

import httpx

_DEFAULT_TIMEOUT = 15.0
_GETME_URL = "https://api.telegram.org/bot{token}/getMe"


def proxy_candidates() -> list[str | None]:
    if os.getenv("TELEGRAM_NO_PROXY", "").strip().lower() in {"1", "true", "yes"}:
        return [None]
    explicit = os.getenv("TELEGRAM_PROXY", "").strip()
    if explicit:
        return [explicit, None]
    gfw = os.getenv("GFW_PROXY", "http://127.0.0.1:7897").strip()
    return [gfw, None]


def check_telegram_getme(
    token: str = "",
    *,
    timeout: float = _DEFAULT_TIMEOUT,
    candidates: list[str | None] | None = None,
    client_factory: Callable[..., httpx.Client] | None = None,
) -> tuple[bool, str]:
    """Return (ok, detail) for Bot API getMe through proxy fallbacks."""
    bot_token = (token or os.getenv("TELEGRAM_BOT_TOKEN", "")).strip()
    if not bot_token:
        return False, "TELEGRAM_BOT_TOKEN not set"

    url = _GETME_URL.format(token=bot_token)
    tries = candidates if candidates is not None else proxy_candidates()
    last_detail = "no transport attempts"

    factory = client_factory or httpx.Client
    for proxy in tries:
        label = proxy or "direct"
        try:
            with factory(proxy=proxy, timeout=timeout, follow_redirects=True) as client:
                response = client.get(url)
                if response.status_code >= 400:
                    last_detail = f"{label}: HTTP {response.status_code}"
                    continue
                payload = response.json()
                if not payload.get("ok"):
                    last_detail = f"{label}: api ok=false"
                    continue
                username = str(payload.get("result", {}).get("username") or "")
                return True, f"{label}: @{username}" if username else f"{label}: ok"
        except httpx.HTTPError as exc:
            last_detail = f"{label}: {type(exc).__name__}"
            continue

    return False, last_detail
