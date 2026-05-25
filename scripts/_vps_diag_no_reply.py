#!/usr/bin/env python3
"""Diagnose WeChat bridge -> LiMa channel no-reply on VPS."""
import os

import paramiko

KEY = os.path.expanduser("~/.ssh/id_ed25519")
SERVER = "47.112.162.80"


def run(cmd: str, timeout: int = 90) -> str:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=30)
    _, o, e = ssh.exec_command(cmd, timeout=timeout)
    out = (o.read() + e.read()).decode(errors="replace").strip()
    ssh.close()
    return out


def main() -> None:
    sections = [
        ("service", "systemctl is-active lima-weixin-ilink lima-router 2>/dev/null; systemctl is-active lima-router || systemctl is-active server 2>/dev/null || true"),
        ("account", "ls -la /root/.hermes/weixin/accounts/*.json 2>/dev/null | head -10"),
        ("bridge_recent", "journalctl -u lima-weixin-ilink --since '30 min ago' --no-pager 2>/dev/null | grep -iE 'msg|reply|channel|error|HTTP|from_user|post_wechat|LiMa|errcode|dead|invite|sender' | tail -40"),
        ("bridge_errors", "journalctl -u lima-weixin-ilink --since '30 min ago' --no-pager 2>/dev/null | grep -iE 'ERROR|WARNING|exception|traceback|failed' | tail -25"),
        ("router_recent", "journalctl -u lima-router --since '30 min ago' --no-pager 2>/dev/null | grep -iE 'wechat|channel|error|500|401' | tail -25 || echo 'no lima-router unit'"),
        ("channel_health", "curl -sS -m 5 http://127.0.0.1:8080/health 2>&1 | head -c 500"),
        ("env_snippet", "grep -E 'LIMA_CHANNEL|WEIXIN|CHANNEL' /opt/lima-router/.env 2>/dev/null | sed 's/=.*/=***/' | head -20"),
        ("relogin", "cat /opt/lima-router/data/weixin_relogin_status.json 2>/dev/null"),
    ]
    for name, cmd in sections:
        print(f"\n=== {name} ===")
        print(run(cmd) or "(empty)")


if __name__ == "__main__":
    main()
