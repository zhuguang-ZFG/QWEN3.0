"""Server runtime bootstrap: fallback call, model constants, shared state."""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.request

from config.backend_config import CLOUDFLARE
from lima_constants import MODEL_ID

MODEL_CREATED = int(time.time())
MAX_BODY_SIZE = 32 * 1024 * 1024  # 32MB — Claude Code sends large contexts


def last_resort_call(messages: list) -> str:
    """Nuclear fallback: direct Cloudflare call, bypasses all routing/health logic."""
    if not CLOUDFLARE.configured:
        return ""
    url = CLOUDFLARE.chat_url()
    body = json.dumps(
        {
            "model": "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
            "messages": messages[-5:],
            "max_tokens": 4096,
        }
    ).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {CLOUDFLARE.token}",
        },
    )
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        data = json.loads(resp.read().decode())
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception as exc:
        logging.warning("[LAST_RESORT] Cloudflare fallback failed: %s", type(exc).__name__)
        return ""


def create_runtime_state() -> tuple[dict, threading.Lock, dict, dict]:
    """Create stats dict, lock, backend map, and loaded module map."""
    stats = {
        "total_requests": 0,
        "backend_calls": {},
        "intent_distribution": {},
        "recent_logs": [],
        "start_time": time.time(),
    }
    return stats, threading.Lock(), {}, {}
