#!/usr/bin/env python3
"""Start long-running OpenClaw WeChat login on VPS; print QR from log."""
from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

import paramiko

KEY = os.path.expanduser("~/.ssh/id_ed25519")
LOG = "/opt/lima-router/data/openclaw_login_live.log"
LOCAL = Path(__file__).resolve().parent.parent / "data" / "openclaw_login_live.log"


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect("47.112.162.80", username="root", key_filename=KEY, timeout=60)

    def r(cmd: str, t: int = 120) -> str:
        _i, o, e = ssh.exec_command(cmd, timeout=t)
        return (o.read() + e.read()).decode("utf-8", errors="replace")

    r("pkill -f 'openclaw channels login' 2>/dev/null; pkill -f openclaw-channels 2>/dev/null; true")
    time.sleep(2)
    r("systemctl stop lima-weixin-ilink 2>/dev/null; systemctl stop lima-openclaw 2>/dev/null; true")
    time.sleep(3)

    start = (
        "nohup bash -lc 'set -a && source /opt/lima-router/.env && set +a && "
        "unset TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID TELEGRAM_WEBHOOK_SECRET && "
        "export OPENCLAW_STATE_DIR=/opt/lima-router/openclaw/state "
        "OPENCLAW_CONFIG_PATH=/opt/lima-router/openclaw/openclaw.json "
        "PATH=/root/.nvm/versions/node/v22.22.1/bin:$PATH && "
        f"openclaw channels login --channel openclaw-weixin --verbose "
        f"> {LOG} 2>&1' </dev/null >/dev/null 2>&1 &"
    )
    print(r(start))
    print("waiting for QR in log...")
    url = ""
    for i in range(18):
        time.sleep(5)
        tail = r(f"tail -50 {LOG} 2>/dev/null || true", t=30)
        m = re.search(r"https://liteapp\.weixin\.qq\.com/[^\s]+", tail)
        if m:
            url = m.group(0)
            break
        if "OK" in tail or "account" in tail.lower():
            break
    full = r(f"cat {LOG} 2>/dev/null | head -80", t=30)
    LOCAL.write_text(full, encoding="utf-8")
    cred = r("find /opt/lima-router/openclaw/state/credentials -type f 2>/dev/null")

    print("\n--- log head ---\n", full[:2500])
    print("\n--- credentials ---\n", cred)
    if url:
        print("\n=== 新扫码链接（后台登录 8 分钟内有效）===\n", url)
    else:
        print("\nWARN: 未在日志中找到 liteapp URL，请查看 log")

    r("systemctl start lima-openclaw; systemctl start lima-weixin-ilink")
    ssh.close()
    return 0 if url else 2


if __name__ == "__main__":
    raise SystemExit(main())
