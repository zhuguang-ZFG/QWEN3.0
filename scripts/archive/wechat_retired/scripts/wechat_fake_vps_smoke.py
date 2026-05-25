#!/usr/bin/env python3
"""Smoke LiMa /channel/wechat on VPS via fake sidecar (no GeWeAPI / no real WeChat)."""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.request

import paramiko

SERVER = os.environ.get("LIMA_VPS_HOST", "47.112.162.80")
REMOTE = "/opt/lima-router"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))


def _read_sidecar_token(ssh: paramiko.SSHClient) -> str:
    _i, o, _e = ssh.exec_command(
        f"grep '^LIMA_WECHAT_SIDECAR_TOKEN=' {REMOTE}/.env | cut -d= -f2-",
        timeout=30,
    )
    return o.read().decode().strip()


def _post(url: str, body: dict, token: str) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def main() -> None:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)
    token = _read_sidecar_token(ssh)
    ssh.close()
    if not token:
        print("missing LIMA_WECHAT_SIDECAR_TOKEN on VPS")
        sys.exit(1)

    base = f"http://{SERVER}:8080"
    sender = "wx-fake-guest-001"
    mid = f"fake-vps-{int(time.time())}"

    r1 = _post(
        f"{base}/channel/v1/wechat/message",
        {
            "message_id": mid,
            "sender_id": sender,
            "conversation_id": sender,
            "conversation_type": "private",
            "text": "你好",
            "timestamp": int(time.time()),
        },
        token,
    )
    print("hello", json.dumps(r1, ensure_ascii=False)[:500])
    if not r1.get("ok"):
        sys.exit(2)

    r2 = _post(
        f"{base}/channel/v1/wechat/message",
        {
            "message_id": mid + "-menu",
            "sender_id": sender,
            "conversation_id": sender,
            "conversation_type": "private",
            "text": "/menu",
            "timestamp": int(time.time()),
        },
        token,
    )
    print("menu", json.dumps(r2, ensure_ascii=False)[:500])
    if r2.get("ok") and r2.get("reply", {}).get("text"):
        print("fake_vps_smoke_passed")
    else:
        sys.exit(3)


if __name__ == "__main__":
    main()
