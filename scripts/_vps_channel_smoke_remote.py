"""VPS-side channel smoke (uploaded by vps_run_channel_smoke.py)."""
import json
import os
import time
import urllib.request

_run = str(int(time.time()))


def read_env(name: str) -> str:
    for path in ("/opt/lima-router/.env", ".env"):
        try:
            with open(path, encoding="utf-8") as handle:
                for line in handle:
                    if line.startswith(name + "="):
                        return line.split("=", 1)[1].strip().strip('"').strip("'")
        except OSError:
            continue
    return os.environ.get(name, "")


def post(path, body, token):
    url = "http://127.0.0.1:8080" + path
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + token,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8", errors="replace"))


def get(path, token):
    url = "http://127.0.0.1:8080" + path
    req = urllib.request.Request(
        url,
        headers={"Authorization": "Bearer " + token},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8", errors="replace"))


token = read_env("LIMA_WECHAT_SIDECAR_TOKEN")
if not token:
    raise SystemExit("missing LIMA_WECHAT_SIDECAR_TOKEN")

h_status, health = get("/channel/v1/wechat/health", token)
assert h_status == 200, health
assert health.get("enabled") is True, health
print("health_ok enabled=1")

_, r1 = post(
    "/channel/v1/wechat/message",
    {
        "message_id": f"vps-smoke-1-{_run}",
        "sender_id": "vps-stranger-1",
        "conversation_id": "vps-conv-1",
        "conversation_type": "private",
        "text": "hello",
        "timestamp": 1,
    },
    token,
)
assert r1.get("ok"), r1
print("auto_guest_ok")

_, r2 = post(
    "/channel/v1/wechat/message",
    {
        "message_id": f"vps-smoke-2-{_run}",
        "sender_id": "vps-stranger-1",
        "conversation_id": "vps-conv-1",
        "conversation_type": "private",
        "text": "/menu",
        "timestamp": 2,
    },
    token,
)
assert r2.get("ok"), r2
menu = (r2.get("reply") or {}).get("text", "")
assert "/百科" in menu, menu[:200]
print("menu_ok")

_, r3 = post(
    "/channel/v1/wechat/message",
    {
        "message_id": f"vps-smoke-3-{_run}",
        "sender_id": "vps-stranger-1",
        "conversation_id": "vps-conv-1",
        "conversation_type": "private",
        "text": "/算 2+2",
        "timestamp": 3,
    },
    token,
)
assert r3.get("ok"), r3
calc = (r3.get("reply") or {}).get("text", "")
assert "4" in calc, calc
print("calc_ok")

_, r4 = post(
    "/channel/v1/wechat/message",
    {
        "message_id": f"vps-smoke-4-{_run}",
        "sender_id": "vps-stranger-1",
        "conversation_id": "vps-conv-1",
        "conversation_type": "private",
        "text": "follow-up turn",
        "timestamp": 4,
    },
    token,
)
assert r4.get("ok"), r4
print("chat_turn_ok")

print("channel_smoke_passed")
