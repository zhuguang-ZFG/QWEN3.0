"""LiMa native device app notification subscription routes."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from device_logic.access import device_access
from device_logic.auth import authorize
from device_logic.db import connect
from device_logic.http import err, new_id, now, read_body, str_field

router = APIRouter(prefix="/device/v1/app", tags=["device-app-notifications"])


def _json_list(value: Any) -> list[str]:
    """Normalize a JSON array or comma-separated string into a string list."""
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("["):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, list):
                    return [str(v) for v in parsed]
            except json.JSONDecodeError:
                pass
        return [stripped] if stripped else []
    return []


@router.post("/notifications/subscribe")
async def subscribe_notifications(
    request: Request,
    authorization: str = Header(default=""),
) -> JSONResponse:
    """Subscribe to WeChat subscription messages for device events."""
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account

    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body

    openid = str_field(body, "openid", "openId")
    template_ids = _json_list(body.get("templateIds", []))
    device_ids = _json_list(body.get("deviceIds", []))
    if not openid or not template_ids:
        return err(400, "openid and templateIds are required", 400)
    if not device_ids:
        return err(400, "deviceIds is required", 400)

    with connect() as conn:
        for did in device_ids:
            if not device_access(conn, account, did):
                return err(403, f"no access to device {did}", 403)

    sub_id = new_id()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO v2_notification_subscription
            (id, account_id, openid, template_ids, device_ids, created_at, updated_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'active')
            """,
            (
                sub_id,
                account["id"],
                openid,
                json.dumps(template_ids, ensure_ascii=False),
                json.dumps(device_ids, ensure_ascii=False),
                now(),
                now(),
            ),
        )
        conn.commit()

    return JSONResponse({"code": 0, "data": {"subscriptionId": sub_id, "status": "active"}})


@router.get("/notifications/subscriptions")
async def list_subscriptions(
    authorization: str = Header(default=""),
) -> JSONResponse:
    """List the current account's active notification subscriptions."""
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account

    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM v2_notification_subscription
            WHERE account_id=? AND status='active'
            ORDER BY created_at DESC
            """,
            (account["id"],),
        ).fetchall()

    return JSONResponse({"code": 0, "data": {"subscriptions": [dict(r) for r in rows], "count": len(rows)}})


@router.delete("/notifications/subscriptions/{sub_id}")
async def unsubscribe(
    sub_id: str,
    authorization: str = Header(default=""),
) -> JSONResponse:
    """Unsubscribe from a notification subscription."""
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account

    with connect() as conn:
        cursor = conn.execute(
            """
            UPDATE v2_notification_subscription
            SET status='unsubscribed', updated_at=?
            WHERE id=? AND account_id=? AND status='active'
            """,
            (now(), sub_id, account["id"]),
        )
        conn.commit()
        if cursor.rowcount == 0:
            return err(404, "subscription not found", 404)

    return JSONResponse({"code": 0, "data": {"subscriptionId": sub_id, "status": "unsubscribed"}})
