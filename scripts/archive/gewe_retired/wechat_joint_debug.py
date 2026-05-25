#!/usr/bin/env python3
"""Joint debug: Gewechat login QR + LiMa sidecar on VPS.

Usage:
  python scripts/wechat_joint_debug.py refresh-qr   # fetch QR, save HTML locally
  python scripts/wechat_joint_debug.py poll-login   # poll login status
  python scripts/wechat_joint_debug.py full-setup   # deploy + QR + instructions
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from wechat_bridge.gewechat_client import GewechatClient

VPS_HOST = os.environ.get("LIMA_VPS_HOST", "47.112.162.80")
QR_HTML_LOCAL = ROOT / "data" / "wechat_login_qr.html"
STATE_FILE = ROOT / "data" / "wechat_gewechat_state.json"


def _load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def _save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _qr_html(b64: str, app_id: str) -> str:
    if b64.startswith("data:"):
        src = b64
    else:
        src = f"data:image/png;base64,{b64}"
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>LiMa 微信登录</title>
<style>body{{font-family:sans-serif;text-align:center;padding:24px}}
img{{max-width:320px;border:1px solid #ddd}}</style></head>
<body>
<h1>LiMa 微信机器人 — 扫码登录</h1>
<p>用<strong>将要当机器人的微信号</strong>扫下方二维码（iPad 登录）。</p>
<img src="{src}" alt="WeChat QR"/>
<p>appId: <code>{app_id}</code></p>
<p>扫码后运行: <code>python scripts/wechat_joint_debug.py poll-login</code></p>
<p>联调：给该号发「你好」或「/menu」，应自动回复。</p>
</body></html>"""


def refresh_qr(*, base_url: str, region_id: str) -> dict:
    preset = os.environ.get("GEWECHAT_TOKEN", "")
    if not preset and STATE_FILE.exists():
        preset = json.loads(STATE_FILE.read_text(encoding="utf-8")).get("gewechat_token", "")
    if not preset and (CREDS := ROOT / "data" / "geweapi_credentials.local.json").exists():
        preset = json.loads(CREDS.read_text(encoding="utf-8")).get("token", "")
    client = GewechatClient(base_url, preset)
    token = client.fetch_token()
    state = _load_state()
    app_id = state.get("app_id", "")
    raw = client.get_login_qr(app_id=app_id, region_id=region_id, retries=60, retry_sleep_s=2.0)
    if raw.get("ret") != 200:
        raise RuntimeError(raw.get("msg", "getLoginQrCode failed"))
    data = raw.get("data") or {}
    app_id = data.get("appId") or app_id
    b64 = data.get("qrImgBase64") or ""
    uuid = data.get("uuid") or ""
    if not b64:
        raise RuntimeError("no qrImgBase64 in response")
    html = _qr_html(b64, app_id)
    QR_HTML_LOCAL.parent.mkdir(parents=True, exist_ok=True)
    QR_HTML_LOCAL.write_text(html, encoding="utf-8")
    state.update({
        "gewechat_token": token,
        "app_id": app_id,
        "uuid": uuid,
        "base_url": base_url,
        "updated_at": int(time.time()),
    })
    _save_state(state)
    return {"token_len": len(token), "app_id": app_id, "html": str(QR_HTML_LOCAL)}


def poll_login() -> dict:
    state = _load_state()
    app_id = state.get("app_id", "")
    base_url = state.get("base_url", "http://127.0.0.1:2531/v2/api")
    token = state.get("gewechat_token", "")
    if not app_id:
        raise RuntimeError("no app_id; run refresh-qr first")
    client = GewechatClient(base_url, token)
    raw = client.check_login(app_id, state.get("uuid", ""))
    return raw


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=["refresh-qr", "poll-login", "full-setup"],
        default="refresh-qr",
        nargs="?",
    )
    parser.add_argument(
        "--gewe-base",
        default=os.environ.get("GEWECHAT_BASE_URL", f"http://{VPS_HOST}:2531/v2/api"),
    )
    parser.add_argument("--region", default=os.environ.get("GEWECHAT_REGION_ID", "330000"))
    args = parser.parse_args()

    if args.command == "refresh-qr":
        info = refresh_qr(base_url=args.gewe_base, region_id=args.region)
        print(json.dumps(info, ensure_ascii=False, indent=2))
        print(f"\n请用浏览器打开: file:///{QR_HTML_LOCAL.as_posix()}")
        print(f"或 VPS 页面: http://{VPS_HOST}:9919/login-qr")
        return

    if args.command == "poll-login":
        raw = poll_login()
        print(json.dumps(raw, ensure_ascii=False, indent=2))
        return

    if args.command == "full-setup":
        import subprocess

        subprocess.run([sys.executable, str(ROOT / "scripts" / "deploy_wechat_sidecar_vps.py")], check=True)
        info = refresh_qr(base_url=args.gewe_base, region_id=args.region)
        print(json.dumps(info, ensure_ascii=False, indent=2))
        print(f"\n=== 联调步骤 ===")
        print(f"1. 打开二维码: file:///{QR_HTML_LOCAL.as_posix()}")
        print(f"   或 http://{VPS_HOST}:9919/login-qr")
        print("2. 微信扫码确认登录（iPad 设备）")
        print("3. 运行: python scripts/wechat_joint_debug.py poll-login")
        print("4. 用另一微信号给机器人号发: 你好  或  /menu")
        print(f"5. 公网 LiMa API smoke: python scripts/vps_https_public_smoke.py")


if __name__ == "__main__":
    main()
