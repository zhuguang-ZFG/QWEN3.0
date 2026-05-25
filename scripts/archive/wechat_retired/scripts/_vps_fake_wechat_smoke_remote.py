"""Run on VPS: fake POST to /channel/v1/wechat/message (localhost:8080)."""
import json
import os
import time
import urllib.request

token = ""
for line in open("/opt/lima-router/.env", encoding="utf-8"):
    if line.startswith("LIMA_WECHAT_SIDECAR_TOKEN="):
        token = line.split("=", 1)[1].strip()
if not token:
    print("no_sidecar_token")
    raise SystemExit(1)

base = "http://127.0.0.1:8080"
sender = "wx-fake-guest-vps"
ts = int(time.time())


def post(text: str, suffix: str) -> dict:
    body = {
        "message_id": f"fake-{ts}-{suffix}",
        "sender_id": sender,
        "conversation_id": sender,
        "conversation_type": "private",
        "text": text,
        "timestamp": ts,
    }
    req = urllib.request.Request(
        base + "/channel/v1/wechat/message",
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + token,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


r1 = post("你好", "hi")
print("hello_ok", r1.get("ok"), (r1.get("reply") or {}).get("text", "")[:80])
r2 = post("/menu", "menu")
print("menu_ok", r2.get("ok"), (r2.get("reply") or {}).get("text", "")[:80])
if r1.get("ok") and r2.get("ok"):
    print("fake_vps_smoke_passed")
else:
    raise SystemExit(2)
