#!/usr/bin/env python3
"""Capture GeWeAPI TokenId via manager console (persistent browser profile).

Usage:
  python scripts/geweapi_capture_token.py
  python scripts/geweapi_capture_token.py --paste <token>
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROFILE = ROOT / "data" / ".geweapi_browser_profile"
OUT = ROOT / "data" / "geweapi_credentials.local.json"
TOKEN_RE = re.compile(r"\b[a-f0-9]{32}\b", re.I)


def save_token(token: str) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"token": token}, indent=2), encoding="utf-8")
    print(f"saved {OUT} token_len={len(token)}")


def capture_interactive() -> str:
    from playwright.sync_api import sync_playwright

    found: list[str] = []

    def on_response(resp) -> None:
        try:
            if "geweapi" not in resp.url:
                return
            body = resp.text()
            for m in TOKEN_RE.findall(body):
                if m not in found:
                    found.append(m)
        except Exception:
            pass

    PROFILE.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(PROFILE),
            headless=False,
            viewport={"width": 1280, "height": 900},
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.on("response", on_response)
        page.goto("http://manager.geweapi.com/#/account/index", wait_until="domcontentloaded", timeout=60000)
        print("已打开 GeWe 控制台。请登录后进入「Token 中心」查看 TokenId。")
        print("关闭浏览器窗口或等待 10 分钟后脚本结束。")
        deadline = time.time() + 600
        while time.time() < deadline:
            if found:
                break
            try:
                if not context.pages:
                    break
                page = context.pages[0]
                for m in TOKEN_RE.findall(page.inner_text("body")):
                    if m not in found:
                        found.append(m)
            except Exception:
                pass
            time.sleep(3)
        try:
            context.close()
        except Exception:
            pass
    return found[0] if found else ""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--paste", default="", help="TokenId pasted from console")
    args = parser.parse_args()

    token = (args.paste or "").strip()
    if not token:
        token = capture_interactive()
    if not token or not TOKEN_RE.fullmatch(token):
        print("未获得有效 Token（32 位十六进制）。")
        print("请注册 http://manager.geweapi.com 后在 Token 中心复制，然后执行：")
        print("  python scripts/geweapi_capture_token.py --paste <你的TokenId>")
        sys.exit(1)
    save_token(token)
    print("Next: python scripts/deploy_geweapi_wechat.py")


if __name__ == "__main__":
    main()
