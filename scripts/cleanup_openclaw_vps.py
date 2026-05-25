#!/usr/bin/env python3
"""Stop and remove LiMa OpenClaw light deploy from VPS."""
from __future__ import annotations

import os
import sys

import paramiko

SERVER = os.environ.get("LIMA_VPS_HOST", "47.112.162.80")
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))
SERVICE = "lima-openclaw"
OC_DIR = "/opt/lima-router/openclaw"


def _run(ssh: paramiko.SSHClient, cmd: str, timeout: float = 120) -> str:
    _stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return (stdout.read() + stderr.read()).decode("utf-8", errors="replace").strip()


def main() -> int:
    if not os.path.isfile(KEY):
        print(f"SSH key not found: {KEY}", file=sys.stderr)
        return 1
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, banner_timeout=30, timeout=60)

    steps = [
        ("stop login", "pkill -f 'openclaw channels login' 2>/dev/null; pkill -f openclaw-channels 2>/dev/null; true"),
        ("stop gateway", f"systemctl stop {SERVICE} 2>/dev/null; systemctl disable {SERVICE} 2>/dev/null; true"),
        ("remove unit", f"rm -f /etc/systemd/system/{SERVICE}.service; systemctl daemon-reload"),
        ("remove tree", f"rm -rf {OC_DIR} /opt/lima-router/data/openclaw_login_*.log /opt/lima-router/data/openclaw_login_*.html /opt/lima-router/data/openclaw_login_*.txt 2>/dev/null; true"),
        ("unlink scripts", "rm -f /opt/lima-router/scripts/openclaw_gateway_start.sh /opt/lima-router/scripts/openclaw_weixin_login_vps.sh"),
        ("ensure ilink", "systemctl start lima-weixin-ilink 2>/dev/null; systemctl start lima-router 2>/dev/null; true"),
    ]
    for name, cmd in steps:
        print(f"=== {name} ===")
        print(_run(ssh, cmd))

    print("=== verify ===")
    print(_run(ssh, f"systemctl is-active {SERVICE} 2>&1 || echo inactive"))
    print(_run(ssh, "pgrep -af openclaw || echo no_openclaw_proc"))
    print(_run(ssh, "ss -tlnp | grep 18789 || echo port_18789_free"))
    print(_run(ssh, "systemctl is-active lima-weixin-ilink lima-router 2>&1"))
    ssh.close()
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
