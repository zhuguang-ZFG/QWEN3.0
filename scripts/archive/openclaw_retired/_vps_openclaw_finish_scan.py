#!/usr/bin/env python3
"""After user scanned QR: stabilize gateway, check login, list pairing."""
from __future__ import annotations

import os
import time

import paramiko

KEY = os.path.expanduser("~/.ssh/id_ed25519")
OC = (
    "bash -lc 'set -a && source /opt/lima-router/.env && set +a && "
    "unset TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID TELEGRAM_WEBHOOK_SECRET && "
    "export OPENCLAW_STATE_DIR=/opt/lima-router/openclaw/state "
    "OPENCLAW_CONFIG_PATH=/opt/lima-router/openclaw/openclaw.json "
    "PATH=/root/.nvm/versions/node/v22.22.1/bin:$PATH && "
)


def main() -> None:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect("47.112.162.80", username="root", key_filename=KEY, timeout=60)

    def r(cmd: str, t: int = 90) -> str:
        _i, o, e = ssh.exec_command(cmd, timeout=t)
        return (o.read() + e.read()).decode("utf-8", errors="replace")

    print("=== credentials ===")
    print(r("find /opt/lima-router/openclaw/state/credentials -type f -exec ls -la {} \\;"))
    print(r("cat /opt/lima-router/openclaw/state/credentials/openclaw-weixin-pairing.json 2>/dev/null"))

    print("\n=== login process ===")
    print(r("pgrep -af 'openclaw-channels|channels login' || echo none"))

    # Free RAM: pause ilink bridge briefly
    print("\n=== stabilize gateway (stop ilink 90s) ===")
    print(r("systemctl stop lima-weixin-ilink"))
    print(r("pkill -f 'openclaw channels login' 2>/dev/null; true"))
    time.sleep(2)
    print(r("systemctl restart lima-openclaw"))
    time.sleep(45)
    print("gateway:", r("systemctl is-active lima-openclaw").strip())
    print("port:", r("ss -tlnp | grep 18789 || echo down"))

    print("\n=== pairing ===")
    print(r(f"{OC}openclaw pairing list openclaw-weixin 2>&1'"))

    print("\n=== if login still running, wait 30s ===")
    if "openclaw-channels" in r("pgrep -af openclaw-channels || true"):
        time.sleep(30)
        print(r("find /opt/lima-router/openclaw/state/credentials -type f"))

    print("\n=== restart ilink bridge ===")
    print(r("systemctl start lima-weixin-ilink"))
    print(r("systemctl is-active lima-weixin-ilink"))

    ssh.close()


if __name__ == "__main__":
    main()
