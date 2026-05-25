"""Persist iLink context_token per peer (required for outbound media/voice)."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from wechat_bridge.weixin_adapter import _hermes_home

log = logging.getLogger(__name__)
_token_store = None


def _get_token_store():
    global _token_store
    if _token_store is None:
        from gateway.platforms.weixin import ContextTokenStore

        _token_store = ContextTokenStore(_hermes_home())
    return _token_store


def restore_account(account_id: str) -> None:
    _get_token_store().restore(account_id)


def save_from_message(account_id: str, message: Dict[str, Any]) -> Optional[str]:
    sender = str(message.get("from_user_id") or "").strip()
    token = str(message.get("context_token") or "").strip()
    if sender and token:
        _get_token_store().set(account_id, sender, token)
        log.debug("context_token saved peer=%s", sender[:12])
    return token or None


def get_token(account_id: str, chat_id: str) -> Optional[str]:
    return _get_token_store().get(account_id, chat_id)
