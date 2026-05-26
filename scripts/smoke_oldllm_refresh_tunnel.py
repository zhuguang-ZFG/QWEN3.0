#!/usr/bin/env python3
"""Smoke OldLLM refresh tunnel VPS loopback -> Windows :4501."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_URL = os.environ.get("OLDLLM_REFRESH_URL", "http://127.0.0.1:4501").rstrip("/")


def main() -> int:
    url = f"{DEFAULT_URL}/refresh"
    print(f"GET {url}")
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            body = resp.read(4096).decode("utf-8", errors="replace")
            print(f"status={resp.status}")
            try:
                payload = json.loads(body)
                if payload.get("token"):
                    payload = {**payload, "token": "[REDACTED]"}
                print(json.dumps(payload, ensure_ascii=False))
                ok = resp.status == 200 and (
                payload.get("ok")
                or payload.get("token_present")
                or bool(payload.get("token"))
            )
            except json.JSONDecodeError:
                print(body[:200])
                ok = resp.status == 200
    except urllib.error.HTTPError as exc:
        print(f"HTTP {exc.code}: {exc.read(300).decode()[:200]}")
        return 1
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"fail: {exc}")
        return 1
    print("oldllm_refresh_tunnel_ok" if ok else "oldllm_refresh_tunnel_fail")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
