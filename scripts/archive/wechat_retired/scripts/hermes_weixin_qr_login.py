#!/usr/bin/env python3
"""Hermes Weixin iLink QR login — saves scannable HTML, polls until confirmed."""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_HTML = ROOT / "data" / "hermes_weixin_login_qr.html"
OUT_STATUS = ROOT / "data" / "hermes_weixin_login_status.json"


def _write_html(qr_url: str, qr_token: str) -> None:
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    safe_url = qr_url.replace("&", "&amp;").replace('"', "&quot;")
    body = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Hermes 微信 iLink 扫码</title>
<style>body{{font-family:sans-serif;max-width:520px;margin:2rem auto;padding:1rem}}
.box{{background:#f5f5f5;padding:1rem;border-radius:8px;word-break:break-all}}</style></head>
<body>
<h1>Hermes 微信登录</h1>
<p>用手机微信扫描下方链接对应的二维码，或在微信里打开链接（若支持）：</p>
<p class="box"><a href="{safe_url}">{safe_url}</a></p>
<p>等待确认中… 本页可刷新查看状态文件。</p>
<p>token: <code>{qr_token[:16]}…</code></p>
</body></html>"""
    OUT_HTML.write_text(body, encoding="utf-8")


def _write_status(**fields: object) -> None:
    payload = {"ts": int(time.time()), **fields}
    OUT_STATUS.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


async def _run() -> int:
    from hermes_constants import get_hermes_home
    from gateway.platforms.weixin import (
        ILINK_BASE_URL,
        EP_GET_BOT_QR,
        EP_GET_QR_STATUS,
        qr_login,
        save_weixin_account,
        check_weixin_requirements,
        _api_get,
    )
    from hermes_cli.config import save_env_value
    import aiohttp
    from gateway.platforms.weixin import _make_ssl_connector, QR_TIMEOUT_MS

    if not check_weixin_requirements():
        print("FAIL: pip install aiohttp cryptography")
        return 1

    home = str(get_hermes_home())
    _write_status(phase="fetching_qr")

    async with aiohttp.ClientSession(trust_env=True, connector=_make_ssl_connector()) as session:
        qr_resp = await _api_get(
            session,
            base_url=ILINK_BASE_URL,
            endpoint=f"{EP_GET_BOT_QR}?bot_type=3",
            timeout_ms=QR_TIMEOUT_MS,
        )
        qrcode_value = str(qr_resp.get("qrcode") or "")
        qrcode_url = str(qr_resp.get("qrcode_img_content") or "")
        if not qrcode_value:
            _write_status(phase="error", msg="no qrcode in response")
            print("FAIL: iLink returned no QR")
            return 1
        scan_data = qrcode_url or qrcode_value
        _write_html(scan_data, qrcode_value)
        print(f"QR page: {OUT_HTML}")
        try:
            import webbrowser
            webbrowser.open(OUT_HTML.as_uri())
        except Exception:
            pass
        _write_status(phase="waiting_scan", qrcode=qrcode_value[:24])

    print("Polling login (up to 8 min). Scan QR on phone now…")
    creds = await qr_login(home, timeout_seconds=480)
    if not creds:
        _write_status(phase="timeout_or_failed")
        print("FAIL: QR login did not complete")
        return 1

    save_env_value("WEIXIN_ACCOUNT_ID", creds["account_id"])
    save_env_value("WEIXIN_TOKEN", creds["token"])
    if creds.get("base_url"):
        save_env_value("WEIXIN_BASE_URL", creds["base_url"])
    save_env_value("WEIXIN_DM_POLICY", "open")
    save_env_value("WEIXIN_ALLOW_ALL_USERS", "true")
    save_env_value("WEIXIN_GROUP_POLICY", "disabled")

    _write_status(phase="ok", account_id=creds["account_id"])
    print(f"OK account_id={creds['account_id']}")
    print("Next: hermes gateway run")
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
