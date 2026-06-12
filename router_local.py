"""Local router model HTTP client (extracted from smart_router.py)."""

from __future__ import annotations

import json
import os
import urllib.request


LM_URL = os.getenv("LOCAL_ROUTER_URL", "http://127.0.0.1:11434/v1/chat/completions")


def call_local(msgs, mt=512, t=0.3):
    """Call local router model (e.g., Ollama) via HTTP."""
    payload = json.dumps(
        {"model": "local-model", "messages": msgs, "max_tokens": mt, "temperature": t}
    ).encode()
    try:
        request = urllib.request.Request(
            LM_URL, data=payload, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        return data["choices"][0]["message"]["content"]
    except Exception as exc:
        return f"[LOCAL_ERR] {exc}"
