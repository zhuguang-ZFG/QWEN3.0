#!/usr/bin/env python3
"""Probe GeWe manager console for login/token page structure (no secrets logged)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "geweapi_probe.json"


def main() -> None:
    from playwright.sync_api import sync_playwright

    result: dict = {"urls": [], "title": "", "needs_login": True, "token_hints": []}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        for url in (
            "http://manager.geweapi.com/#/account/index",
            "http://manager.geweapi.com/",
        ):
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                result["urls"].append({"url": url, "final": page.url, "title": page.title()})
            except Exception as exc:
                result["urls"].append({"url": url, "error": type(exc).__name__})
        result["title"] = page.title()
        text = page.inner_text("body")[:4000]
        for kw in ("Token", "token", "登录", "注册", "试用", "扫码"):
            if kw in text:
                result["token_hints"].append(kw)
        result["needs_login"] = any(x in text for x in ("登录", "注册", "sign", "Login"))
        (ROOT / "data").mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(ROOT / "data" / "geweapi_manager.png"), full_page=True)
        browser.close()
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
