#!/usr/bin/env python3
"""Check OpenClaw state after WeChat QR scan."""
from __future__ import annotations

import json
import os
from pathlib import Path

import paramiko

KEY = os.path.expanduser("~/.ssh/id_ed25519")
ENV = (
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
        i, o, e = ssh.exec_command(cmd, timeout=t)
        return (o.read() + e.read()).decode("utf-8", errors="replace")

    cmds = [
        ("gateway", "systemctl is-active lima-openclaw; ss -tlnp | grep 18789 || true"),
        ("pairing", f"{ENV}openclaw pairing list openclaw-weixin 2>&1'"),
        ("channels", f"{ENV}openclaw channels list 2>&1'"),
        ("status", f"{ENV}openclaw status 2>&1 | head -80'"),
        ("accounts", "find /opt/lima-router/openclaw/state -maxdepth 4 -type f 2>/dev/null | head -40"),
        ("weixin_creds", "ls -la /opt/lima-router/openclaw/state/credentials 2>/dev/null; ls -la /opt/lima-router/openclaw/state/credentials/openclaw-weixin 2>/dev/null || true"),
        ("journal", "journalctl -u lima-openclaw -n 25 --no-pager 2>&1"),
        ("login_proc", "pgrep -af 'openclaw.*login|openclaw-channels' || echo none"),
    ]
    for name, cmd in cmds:
        print(f"\n===== {name} =====\n{r(cmd)[:3500]}")

    # Try read weixin account json if present
    cred_dir = r("ls /opt/lima-router/openclaw/state/credentials/openclaw-weixin 2>/dev/null || ls /root/.openclaw/credentials 2>/dev/null || true")
    print(f"\n===== cred listing =====\n{cred_dir}")

    # Poll login completion
    print("\n===== poll 60s =====")
    for i in range(6):
        import time
        time.sleep(10)
        cred = r(
            "find /opt/lima-router/openclaw/state/credentials -type f 2>/dev/null | head -20"
        )
        proc = r("pgrep -af openclaw-channels 2>/dev/null || echo none")
        print(f"t+{(i+1)*10}s proc={proc.strip()[:120]}")
        print(f"  cred={cred.strip()[:300]}")

    ssh.close()


if __name__ == "__main__":
    main()
