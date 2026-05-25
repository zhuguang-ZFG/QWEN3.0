"""Bind WeixinAdapter to the bridge long-poll session for CDN media send."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)


def _hermes_home() -> str:
    try:
        from hermes_constants import get_hermes_home

        return str(get_hermes_home())
    except Exception:
        return os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))


def ensure_live_adapter(
    *,
    session,
    token: str,
    account_id: str,
    base_url: str,
    cdn_base_url: str,
    extra: Optional[Dict[str, Any]] = None,
):
    """Register (or refresh) adapter on gateway _LIVE_ADAPTERS for this token."""
    from gateway.platforms.weixin import (
        WeixinAdapter,
        PlatformConfig,
        ContextTokenStore,
        _LIVE_ADAPTERS,
    )

    existing = _LIVE_ADAPTERS.get(token)
    if existing is not None and getattr(existing, "_send_session", None) is session:
        return existing

    merged = {**(extra or {}), "account_id": account_id, "base_url": base_url, "cdn_base_url": cdn_base_url}
    adapter = WeixinAdapter(
        PlatformConfig(enabled=True, token=token, extra=merged),
    )
    adapter._send_session = session
    adapter._session = session
    adapter._token = token
    adapter._account_id = account_id
    adapter._base_url = base_url.rstrip("/")
    adapter._cdn_base_url = cdn_base_url.rstrip("/")
    adapter._token_store = ContextTokenStore(_hermes_home())
    adapter._token_store.restore(account_id)
    _LIVE_ADAPTERS[token] = adapter
    log.debug("live Weixin adapter bound token=%s…", token[:8])
    return adapter


def clear_live_adapter(token: str) -> None:
    from gateway.platforms.weixin import _LIVE_ADAPTERS

    _LIVE_ADAPTERS.pop(token, None)
