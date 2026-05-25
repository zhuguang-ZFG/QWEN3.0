"""iLink typing indicator for LiMa Weixin bridge."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

_ticket_cache: Dict[str, str] = {}


async def show_typing(
    session,
    *,
    base_url: str,
    token: str,
    chat_id: str,
    message: Optional[dict] = None,
) -> None:
    if not chat_id or not token:
        return
    try:
        from gateway.platforms.weixin import (
            TYPING_START,
            _get_config,
            _send_typing,
            CONFIG_TIMEOUT_MS,
        )
    except ImportError:
        return

    context_token = ""
    if message:
        context_token = str(message.get("context_token") or "").strip()

    ticket = _ticket_cache.get(chat_id)
    if not ticket:
        try:
            cfg = await _get_config(
                session,
                base_url=base_url,
                token=token,
                user_id=chat_id,
                context_token=context_token or None,
            )
            ticket = str(cfg.get("typing_ticket") or "").strip()
            if ticket:
                _ticket_cache[chat_id] = ticket
        except Exception as exc:
            log.debug("getConfig typing_ticket failed: %s", exc)
            return

    if not ticket:
        return

    try:
        await _send_typing(
            session,
            base_url=base_url,
            token=token,
            to_user_id=chat_id,
            typing_ticket=ticket,
            status=TYPING_START,
        )
    except Exception as exc:
        log.debug("typing start failed: %s", exc)


async def hide_typing(
    session,
    *,
    base_url: str,
    token: str,
    chat_id: str,
) -> None:
    ticket = _ticket_cache.get(chat_id)
    if not ticket or not token:
        return
    try:
        from gateway.platforms.weixin import TYPING_STOP, _send_typing
    except ImportError:
        return
    try:
        await _send_typing(
            session,
            base_url=base_url,
            token=token,
            to_user_id=chat_id,
            typing_ticket=ticket,
            status=TYPING_STOP,
        )
    except Exception as exc:
        log.debug("typing stop failed: %s", exc)
