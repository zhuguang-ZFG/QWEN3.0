"""Cloudflare vision calls for legacy router_http (CQ-096)."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request

from response_cleaner import clean_response
from router_circuit_breaker import cb_record
from vision_handler import detect_vision_request

DEBUG = os.environ.get("LIMA_DEBUG", "") == "1"


def has_vision_content(messages: list) -> bool:
    return detect_vision_request(messages)


def call_cf_vision(msgs, mt, started: float):
    cf_token = os.environ.get("CLOUDFLARE_TOKEN", "")
    cf_account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
    if not cf_token or not cf_account:
        return None
    url = (
        f"https://api.cloudflare.com/client/v4/accounts/{cf_account}/ai/run/"
        "@cf/meta/llama-3.2-11b-vision-instruct"
    )
    body = json.dumps({"messages": msgs, "max_tokens": mt}).encode()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {cf_token}",
        "User-Agent": "LiMa/2.0",
    }
    try:
        request = urllib.request.Request(url, data=body, headers=headers)
        with urllib.request.urlopen(request, timeout=15) as resp:
            payload = json.loads(resp.read().decode())
        answer = payload.get("result", {}).get("response", "")
        if answer:
            cb_record("cf_vision", True, int((time.time() - started) * 1000))
            return clean_response(answer, "cf_vision")
        return None
    except Exception as exc:
        if DEBUG:
            print(f"[DEBUG] cf_vision error: {exc}", file=sys.stderr)
        cb_record("cf_vision", False)
        return None
