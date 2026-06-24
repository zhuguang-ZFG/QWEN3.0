#!/usr/bin/env python3
"""Response examples for sharing, transfers, members, sessions and notifications."""

from __future__ import annotations

from typing import Any

from .shared import uuid


def _resp_chat_sessions_list() -> Any:
    return {"sessions": [{"id": uuid("sess"), "title": "New chat"}]}


def _resp_chat_sessions_create() -> Any:
    return {"id": uuid("sess"), "title": "New chat"}


def _resp_chat_session_messages() -> Any:
    return {"messages": [{"role": "user", "content": "Hi"}]}


def _resp_chat_session_delete() -> Any:
    return {"deleted": True}


def _resp_members_create() -> Any:
    return {"member_id": uuid("mbr"), "role": "member"}


def _resp_transfers_pending() -> Any:
    return {"transfers": [{"id": uuid("trf"), "device_name": "Bedroom"}]}


def _resp_transfer_accept() -> Any:
    return {"transfer_id": uuid("trf"), "status": "accepted"}


def _resp_transfer_cancel() -> Any:
    return {"transfer_id": uuid("trf"), "status": "cancelled"}


def _resp_device_transfer() -> Any:
    return {"transfer_id": uuid("trf"), "expires_in": 86400}


def _resp_device_shares() -> Any:
    return {"shares": [{"token": uuid("shr"), "role": "viewer"}]}


def _resp_device_share_create() -> Any:
    return {"share_token": uuid("shr"), "status": "active"}


def _resp_device_share_revoke() -> Any:
    return {"revoked": True}


def _resp_share_accept() -> Any:
    return {"share_token": uuid("shr"), "status": "accepted"}


def _resp_notifications_subscribe() -> Any:
    return {"subscription_id": uuid("sub"), "status": "active"}


def _resp_notifications_subscriptions() -> Any:
    return {"subscriptions": [{"id": uuid("sub"), "type": "push"}]}


def _resp_notifications_subscription_delete() -> Any:
    return {"deleted": True}


def _resp_stats_overview() -> Any:
    return {"total_devices": 1, "total_tasks": 42}
