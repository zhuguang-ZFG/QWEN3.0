"""Apprise multi-channel notify bridge (optional dependency, default off)."""

from __future__ import annotations

import logging
import os

_log = logging.getLogger(__name__)


def apprise_enabled() -> bool:
    return os.environ.get("LIMA_APPRISE_ENABLED", "0").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def apprise_urls() -> list[str]:
    raw = os.environ.get("LIMA_APPRISE_URLS", "").strip()
    if not raw:
        return []
    return [part.strip() for part in raw.replace("\n", ",").split(",") if part.strip()]


def notify(
    body: str,
    *,
    title: str = "LiMa",
    urls: list[str] | None = None,
) -> tuple[bool, str]:
    """Send via Apprise. Returns (ok, detail)."""
    targets = urls or apprise_urls()
    if not targets:
        return False, "no_urls"

    try:
        import apprise
    except ImportError:
        _log.debug("apprise not installed")
        return False, "apprise_not_installed"

    client = apprise.Apprise()
    for url in targets:
        if not client.add(url):
            return False, f"invalid_url:{url[:40]}"

    sent = client.notify(body=body, title=title)
    if sent:
        return True, "sent"
    return False, "send_failed"
