"""Forward normalized messages to LiMa Channel Gateway."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


def post_wechat_message(
    *,
    base_url: str,
    sidecar_token: str,
    message_id: str,
    sender_id: str,
    conversation_id: str,
    text: str,
    timestamp: int,
    attachments: list | None = None,
) -> dict:
    body = {
        "message_id": message_id,
        "sender_id": sender_id,
        "conversation_id": conversation_id,
        "conversation_type": "private",
        "text": text,
        "timestamp": timestamp,
    }
    if attachments:
        body["attachments"] = attachments
    url = base_url.rstrip("/") + "/channel/v1/wechat/message"
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {sidecar_token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        return {"ok": False, "error": f"HTTP {exc.code}", "body": raw[:500]}


def lima_base_url() -> str:
    return os.environ.get("LIMA_CHANNEL_BASE_URL", "http://127.0.0.1:8080").rstrip("/")


def lima_sidecar_token() -> str:
    return os.environ.get("LIMA_WECHAT_SIDECAR_TOKEN", "").strip()
