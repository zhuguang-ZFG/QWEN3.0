"""WeChat subscription-message notifications for device events."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import time
from typing import Any

import httpx

from device_logic.access import check_share_permission, is_owner
from device_logic.db import connect
from device_logic.http import new_id, now

_log = logging.getLogger(__name__)

_background_tasks: set[asyncio.Task] = set()

_WX_ACCESS_TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token"
_WX_SUBSCRIBE_MSG_URL = "https://api.weixin.qq.com/cgi-bin/message/subscribe/send"

NOTIFICATION_TEMPLATES: dict[str, dict[str, Any]] = {
    "task_completed": {
        "template_id": "",
        "title": "任务完成",
        "body": "您的设备已完成「{task_name}」任务",
        "page": "pages/tasks/detail?id={task_id}",
        "data_keys": {"thing1": "task_name", "time2": "completed_at"},
    },
    "task_failed": {
        "template_id": "",
        "title": "任务失败",
        "body": "设备执行「{task_name}」时出错：{error}",
        "page": "pages/tasks/detail?id={task_id}",
        "data_keys": {"thing1": "task_name", "thing2": "error"},
    },
    "device_offline": {
        "template_id": "",
        "title": "设备离线",
        "body": "设备 {device_name} 已断开连接",
        "page": "pages/devices/detail?id={device_id}",
        "data_keys": {"thing1": "device_name", "time2": "offline_at"},
    },
    "firmware_update": {
        "template_id": "",
        "title": "固件更新",
        "body": "设备 {device_name} 有新固件 v{version} 可用",
        "page": "pages/devices/detail?id={device_id}",
        "data_keys": {"thing1": "device_name", "thing2": "version"},
    },
}


def _wx_appid() -> str:
    return os.environ.get("LIMA_WX_APPID", "")


def _wx_secret() -> str:
    return os.environ.get("LIMA_WX_SECRET", "")


class WeChatNotifier:
    """Send WeChat mini-program subscription messages with access-token caching."""

    def __init__(self) -> None:
        self._access_token: str = ""
        self._token_expires: float = 0.0

    async def _get_access_token(self) -> str:
        """Fetch a cached WeChat access_token or request a new one."""
        if self._access_token and time.time() < self._token_expires - 60:
            return self._access_token

        appid = _wx_appid()
        secret = _wx_secret()
        if not appid or not secret:
            _log.warning("wechat appid/secret not configured; cannot fetch access_token")
            return ""

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    _WX_ACCESS_TOKEN_URL,
                    params={
                        "grant_type": "client_credential",
                        "appid": appid,
                        "secret": secret,
                    },
                    timeout=10,
                )
                data = resp.json()
        except Exception as exc:
            _log.warning("wechat access_token request failed: %s", exc, exc_info=True)
            return ""

        if "access_token" not in data:
            _log.error("wechat access_token request rejected: %s", data)
            return ""

        self._access_token = data["access_token"]
        self._token_expires = time.time() + data.get("expires_in", 7200)
        return self._access_token

    def _build_payload(
        self,
        openid: str,
        tmpl: dict[str, Any],
        data: dict[str, str],
        page: str,
    ) -> dict[str, Any]:
        wx_data = {wx_key: {"value": data.get(data_key, "")} for wx_key, data_key in tmpl["data_keys"].items()}

        # page 模板引用的 key（如 task_id）不保证在 data 里；format_map 容错，
        # 缺 key 时留空而非抛 KeyError（后台任务里异常会无声丢失）。
        class _Defaulting(dict):
            def __missing__(self, key: str) -> str:
                return ""

        return {
            "touser": openid,
            "template_id": tmpl["template_id"],
            "page": page or tmpl["page"].format_map(_Defaulting(data)),
            "data": wx_data,
            "miniprogram_state": "formal",
        }

    async def send_subscribe_message(
        self,
        openid: str,
        template_key: str,
        data: dict[str, str],
        page: str = "",
    ) -> dict[str, Any]:
        """Send one subscription message if the template is configured."""
        tmpl = NOTIFICATION_TEMPLATES.get(template_key)
        if not tmpl:
            _log.warning("notification template '%s' not defined", template_key)
            return {"status": "failed", "error": "template_not_defined"}
        if not tmpl["template_id"]:
            _log.warning("notification template '%s' not configured", template_key)
            return {"status": "failed", "error": "template_not_configured"}
        if not _wx_appid() or not _wx_secret():
            _log.warning("wechat appid/secret not configured; skipping notification")
            return {"status": "failed", "error": "wechat_not_configured"}

        token = await self._get_access_token()
        if not token:
            return {"status": "failed", "error": "no_access_token"}

        payload = self._build_payload(openid, tmpl, data, page)
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    _WX_SUBSCRIBE_MSG_URL,
                    params={"access_token": token},
                    json=payload,
                    timeout=10,
                )
                result = resp.json()
        except Exception as exc:
            _log.error("wechat subscribe message request failed: %s", exc, exc_info=True)
            return {"status": "failed", "error": str(exc)}

        if result.get("errcode", 0) != 0:
            _log.error("wechat subscribe message rejected: %s", result)
            return {"status": "failed", "wx_response": result}
        return {"status": "sent", "wx_response": result}


notifier = WeChatNotifier()


def _subscription_matches(row: sqlite3.Row, device_id: str, event_type: str) -> bool:
    """Check whether a subscription row matches the given device and event type."""
    import json as _json

    template_ids = _json.loads(row["template_ids"] or "[]")
    if event_type not in template_ids:
        return False

    device_ids_text = row["device_ids"]
    if not device_ids_text:
        return False

    device_ids = _json.loads(device_ids_text)
    return device_id in device_ids


def _subscription_has_access(conn: sqlite3.Connection, row: sqlite3.Row, device_id: str) -> bool:
    # 加载完整 account（含 role）以支持 admin 快路径
    from device_logic.auth import load_active_account

    account = load_active_account(row["account_id"])
    if not isinstance(account, dict):
        return False
    return is_owner(conn, account, device_id) or check_share_permission(conn, device_id, row["account_id"], "view")


async def dispatch_notification(
    device_id: str,
    event_type: str,
    data: dict[str, str],
) -> None:
    """Dispatch notifications to all subscribers for a device event."""
    tmpl = NOTIFICATION_TEMPLATES.get(event_type)
    if not tmpl:
        return

    def _query_matched() -> list[sqlite3.Row]:
        with connect() as conn:
            rows = conn.execute("SELECT * FROM v2_notification_subscription WHERE status='active'").fetchall()
            return [
                row
                for row in rows
                if _subscription_matches(row, device_id, event_type) and _subscription_has_access(conn, row, device_id)
            ]

    matched = await asyncio.to_thread(_query_matched)

    if not matched:
        return

    for row in matched:
        result = await notifier.send_subscribe_message(
            openid=row["openid"],
            template_key=event_type,
            data=data,
        )
        # 同步 SQLite 写会阻塞事件循环，与上面的读路径一样丢线程池。
        await asyncio.to_thread(_log_notification, device_id, event_type, row, tmpl, data, result)


def _log_notification(
    device_id: str,
    event_type: str,
    row: sqlite3.Row,
    tmpl: dict[str, Any],
    data: dict[str, str],
    result: dict[str, Any],
) -> None:
    """Persist a notification attempt to v2_notification_log."""
    try:
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO v2_notification_log
                (id, account_id, device_id, event_type, template_id, payload, sent_at, status, error, wx_response)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id(),
                    row["account_id"],
                    device_id,
                    event_type,
                    tmpl["template_id"],
                    json.dumps(data, ensure_ascii=False),
                    now(),
                    result.get("status", "failed"),
                    result.get("error", ""),
                    json.dumps(result.get("wx_response", {}) or {}, ensure_ascii=False),
                ),
            )
            conn.commit()
    except Exception as exc:
        _log.warning("failed to write notification log: %s", exc, exc_info=True)


def _on_background_done(task: asyncio.Task) -> None:
    """Retrieve and log background-dispatch exceptions instead of losing them."""
    _background_tasks.discard(task)
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        _log.error("background notification dispatch failed: %s", exc, exc_info=exc)


def dispatch_notification_later(
    device_id: str,
    event_type: str,
    data: dict[str, str],
) -> None:
    """Best-effort schedule an async dispatch from a synchronous caller."""
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            task = loop.create_task(dispatch_notification(device_id, event_type, data))
            _background_tasks.add(task)
            task.add_done_callback(_on_background_done)
        else:
            _log.warning("event loop not running; skipping notification for device=%s", device_id)
    except RuntimeError:
        _log.warning("no event loop; skipping notification for device=%s", device_id)
    except Exception as exc:
        _log.warning("notification scheduling failed for device=%s: %s", device_id, exc, exc_info=True)
