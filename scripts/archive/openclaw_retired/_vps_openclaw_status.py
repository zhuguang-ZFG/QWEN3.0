#!/usr/bin/env python3
import os
import paramiko

KEY = os.path.expanduser("~/.ssh/id_ed25519")
cmds = [
    "dmesg -T 2>/dev/null | tail -15",
    "ps aux --sort=-%mem | head -10",
    "systemctl is-active lima-openclaw",
    "systemctl status lima-openclaw --no-pager 2>&1 | head -18",
    "journalctl -u lima-openclaw -n 35 --no-pager",
    "ss -tlnp | grep 18789 || true",
    "test -n \"$LIMA_API_KEY\" && echo LIMA_API_KEY_set || echo LIMA_API_KEY_missing",
    "bash -lc 'set -a; source /opt/lima-router/.env; set +a; test -n \"$LIMA_API_KEY\" && echo sourced_ok'",
]
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("47.112.162.80", username="root", key_filename=KEY, timeout=60)
for c in cmds:
    i, o, e = ssh.exec_command(c, timeout=60)
    out = (o.read() + e.read()).decode()
    print(f"\n>>> {c}\n{out[:3000]}")
ssh.close()
