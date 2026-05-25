#!/usr/bin/env python3
"""Fetch iLink bot add-friend QR and write shareable HTML for owners."""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_HTML = ROOT / "data" / "weixin_share_qr.html"
OUT_JSON = ROOT / "data" / "weixin_share_qr.json"


def _write_html(qr_url: str, account_id: str) -> None:
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    safe = qr_url.replace("&", "&amp;").replace('"', "&quot;")
    body = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>添加 LiMa 微信助手</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{{font-family:sans-serif;max-width:520px;margin:1.5rem auto;padding:1rem;line-height:1.6}}
.box{{background:#f0f7ff;padding:1rem;border-radius:8px;word-break:break-all}}
.note{{color:#555;font-size:0.95rem}}</style></head>
<body>
<h1>添加 LiMa 微信助手</h1>
<p class="note">iLink 机器人不能当普通好友名片转发，请用微信扫一扫本页链接。</p>
<p class="box"><a href="{safe}">{safe}</a></p>
<p>机器人 ID：<code>{account_id}</code></p>
<p>添加后直接发「你好」或「帮助」即可使用。</p>
</body></html>"""
    OUT_HTML.write_text(body, encoding="utf-8")


async def _run() -> int:
    from gateway.platforms.weixin import (
        ILINK_BASE_URL,
        EP_GET_BOT_QR,
        check_weixin_requirements,
        _api_get,
        _make_ssl_connector,
        QR_TIMEOUT_MS,
    )
    import aiohttp

    if not check_weixin_requirements():
        print("FAIL: pip install aiohttp cryptography")
        return 1

    account_id = ""
    try:
        home = Path.home() / ".hermes" / "weixin" / "accounts"
        for p in sorted(home.glob("*.json")):
            if "context" not in p.name and "sync" not in p.name:
                data = json.loads(p.read_text(encoding="utf-8"))
                account_id = p.stem
                break
    except Exception:
        pass

    async with aiohttp.ClientSession(trust_env=True, connector=_make_ssl_connector()) as session:
        qr_resp = await _api_get(
            session,
            base_url=ILINK_BASE_URL,
            endpoint=f"{EP_GET_BOT_QR}?bot_type=3",
            timeout_ms=QR_TIMEOUT_MS,
        )
    qrcode_value = str(qr_resp.get("qrcode") or "")
    qrcode_url = str(qr_resp.get("qrcode_img_content") or "")
    if not qrcode_url and not qrcode_value:
        print("FAIL: no QR from iLink")
        return 1

    share_url = qrcode_url or qrcode_value
    _write_html(share_url, account_id or "见登录账号")
    payload = {
        "ts": int(time.time()),
        "account_id": account_id,
        "share_url": share_url,
        "html": str(OUT_HTML),
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK account_id={account_id}")
    print(f"share_url={share_url[:120]}...")
    print(f"HTML: {OUT_HTML}")
    print("Send the HTML file or link to friends; they scan with WeChat to add the bot.")
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
