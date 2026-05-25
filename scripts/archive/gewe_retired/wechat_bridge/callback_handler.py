"""Parse Gewechat webhook payloads and reply via LiMa."""

from __future__ import annotations

import time
from typing import Any, Optional

from wechat_bridge.gewechat_client import GewechatClient
from wechat_bridge.lima_client import post_wechat_message


def _nested_string(obj: Any, *keys: str) -> str:
    cur = obj
    for key in keys:
        if not isinstance(cur, dict):
            return ""
        cur = cur.get(key)
    return str(cur or "").strip()


def parse_inbound(payload: dict) -> Optional[dict]:
    if payload.get("TypeName") != "AddMsg":
        return None
    data = payload.get("Data") or {}
    if int(data.get("MsgType") or 0) != 1:
        return None
    wxid = str(payload.get("Wxid") or "")
    from_user = _nested_string(data, "FromUserName", "string")
    if not from_user or from_user == wxid:
        return None
    if from_user.endswith("@chatroom"):
        return None
    text = _nested_string(data, "Content", "string")
    if not text:
        return None
    msg_id = str(data.get("NewMsgId") or data.get("MsgId") or int(time.time() * 1000))
    return {
        "app_id": str(payload.get("Appid") or ""),
        "sender_id": from_user,
        "conversation_id": from_user,
        "text": text,
        "message_id": f"gewe-{msg_id}",
        "reply_wxid": from_user,
    }


def handle_callback(
    payload: dict,
    *,
    gewe: GewechatClient,
    lima_base: str,
    lima_token: str,
) -> dict:
    inbound = parse_inbound(payload)
    if inbound is None:
        return {"ok": True, "skipped": True}
    result = post_wechat_message(
        base_url=lima_base,
        sidecar_token=lima_token,
        message_id=inbound["message_id"],
        sender_id=inbound["sender_id"],
        conversation_id=inbound["conversation_id"],
        text=inbound["text"],
        timestamp=int(time.time()),
    )
    reply_text = ""
    if result.get("ok") and isinstance(result.get("reply"), dict):
        reply_text = str(result["reply"].get("text") or "")
    elif result.get("error"):
        reply_text = f"LiMa: {result.get('error')}"
    else:
        reply_text = "LiMa: empty response"
    app_id = inbound.get("app_id") or ""
    if app_id and reply_text:
        try:
            gewe.post_text(app_id, inbound["reply_wxid"], reply_text[:4000])
        except Exception as exc:
            return {"ok": False, "lima_ok": result.get("ok"), "send_error": type(exc).__name__}
    return {"ok": True, "lima_ok": result.get("ok"), "replied": bool(reply_text)}
