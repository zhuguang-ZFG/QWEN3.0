#!/usr/bin/env python3
"""Read-only smoke for lima-openclaw on VPS."""

from __future__ import annotations

import os
import sys

import paramiko

SERVER = os.environ.get("LIMA_VPS_HOST", "47.112.162.80")
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))
OC_STATE = "/opt/lima-router/openclaw/state"
OC_CFG = "/opt/lima-router/openclaw/openclaw.json"
NVM_BIN = "/root/.nvm/versions/node/v22.22.1/bin"


def _run(ssh: paramiko.SSHClient, cmd: str) -> str:
    _stdin, stdout, stderr = ssh.exec_command(cmd, timeout=90)
    return (stdout.read() + stderr.read()).decode("utf-8", errors="replace").strip()


def _oc(cmd: str) -> str:
    inner = (
        f"set -a && source /opt/lima-router/.env && set +a && "
        f"unset TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID TELEGRAM_WEBHOOK_SECRET && "
        f"export OPENCLAW_STATE_DIR={OC_STATE} OPENCLAW_CONFIG_PATH={OC_CFG} "
        f"PATH={NVM_BIN}:$PATH && {cmd}"
    )
    return f"bash -lc {_shell_quote(inner)}"


def _shell_quote(s: str) -> str:
    return "'" + s.replace("'", "'\"'\"'") + "'"


def main() -> int:
    if not os.path.isfile(KEY):
        print(f"no key: {KEY}", file=sys.stderr)
        return 1
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)

    checks = [
        ("systemd", "systemctl is-active lima-openclaw"),
        ("port", "ss -tlnp | grep 18789 || true"),
        ("doctor", _oc("openclaw doctor --lint 2>&1")),
        ("channels", _oc("openclaw channels list 2>&1")),
        ("lima-router", "curl -sf http://127.0.0.1:8080/health | head -c 200"),
        ("ilink-bridge", "systemctl is-active lima-weixin-ilink"),
    ]
    failed = 0
    for name, cmd in checks:
        out = _run(ssh, cmd)
        print(f"\n--- {name} ---\n{out[:2000]}")
        if name == "systemd" and out.strip() != "active":
            failed += 1
        if name == "port" and "18789" not in out:
            failed += 1
    ssh.close()
    print("\n" + ("FAIL" if failed else "OK (WeChat QR login still pending)"))
    return failed


if __name__ == "__main__":
    raise SystemExit(main())
