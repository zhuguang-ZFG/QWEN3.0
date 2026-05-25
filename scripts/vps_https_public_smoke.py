#!/usr/bin/env python3
"""Public HTTPS smoke (chat API). Channel API stays Bearer-only on VPS localhost."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

CHAT_BASE = os.environ.get("LIMA_PUBLIC_CHAT_BASE", "https://chat.donglicao.com")
FRP_BASE = os.environ.get("LIMA_FRP_BASE", "http://47.112.162.80:8088")


def _get(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, resp.read(300).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(300).decode("utf-8", errors="replace")


def main() -> None:
    checks = []
    for label, url in [
        ("chat_health", f"{CHAT_BASE}/health"),
        ("frp_health", f"{FRP_BASE}/health"),
    ]:
        code, body = _get(url)
        ok = code == 200 and "ok" in body.lower()
        checks.append((label, ok, code, body[:120]))
        print(f"{label}: {code} {'OK' if ok else 'FAIL'} {body[:80]}")

    if not all(c[1] for c in checks):
        raise SystemExit(1)
    print("public_https_smoke_ok")


if __name__ == "__main__":
    main()
