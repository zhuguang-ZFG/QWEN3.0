"""Run on VPS: fetch Gewechat QR and push HTML into sidecar + set callback."""
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, "/opt/lima-router")
from wechat_bridge.gewechat_client import GewechatClient
from wechat_bridge import sidecar_server


def _ensure_gewe_api() -> None:
    subprocess.run(["bash", "/opt/lima-router/_vps_gewe_bootstrap.sh"], check=False, timeout=180)


def read_env(name: str) -> str:
    for path in ("/opt/lima-router/.env",):
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.startswith(name + "="):
                    return line.split("=", 1)[1].strip()
    return ""


import os

base = read_env("GEWECHAT_BASE_URL") or os.environ.get("GEWECHAT_BASE_URL") or "http://127.0.0.1:2531/v2/api"
cb = read_env("GEWECHAT_CALLBACK_URL") or "https://chat.donglicao.com/gewe/v2/api/callback/collect"
preset = read_env("GEWECHAT_TOKEN") or os.environ.get("GEWECHAT_TOKEN", "")
client = GewechatClient(base, preset)
if "geweapi.com" not in base.lower():
    _ensure_gewe_api()
token = ""
for _ in range(10):
    try:
        token = client.fetch_token()
        break
    except Exception:
        if "geweapi.com" in base.lower():
            break
        _ensure_gewe_api()
        time.sleep(5)
if not token:
    print("token_fail")
    raise SystemExit(1)
try:
    client.set_callback(cb)
except Exception as exc:
    print("callback_warn", type(exc).__name__)
raw = {}
for attempt in range(1, 61):
    try:
        raw = client.get_login_qr(region_id="330000")
    except Exception as exc:
        print("qr_http_err", attempt, type(exc).__name__)
        _ensure_gewe_api()
        time.sleep(5)
        continue
    if raw.get("ret") == 200:
        break
    print("qr_retry", attempt, raw.get("msg", ""), (raw.get("data") or {}).get("msg", ""))
    time.sleep(3)
if raw.get("ret") != 200:
    print("qr_fail", raw)
    raise SystemExit(1)
data = raw.get("data") or {}
b64 = data.get("qrImgBase64") or ""
app_id = data.get("appId") or ""
src = b64 if b64.startswith("data:") else f"data:image/png;base64,{b64}"
html = f"""<!DOCTYPE html><html><head><meta charset=utf-8><title>LiMa微信登录</title></head>
<body style=text-align:center><h1>LiMa 微信机器人登录</h1>
<p>用将要当机器人的微信号扫码</p><img src="{src}" width=300><p>appId={app_id}</p></body></html>"""
sidecar_server.set_qr_html(html, app_id=app_id, gewe_token=token)
state = {"app_id": app_id, "uuid": data.get("uuid"), "gewechat_token": token}
state_path = Path("/opt/lima-router/data/wechat_gewechat_state.json")
state_path.parent.mkdir(parents=True, exist_ok=True)
state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
# mirror QR to local pull path marker
print("qr_ok", app_id)
