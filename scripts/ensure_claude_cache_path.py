#!/usr/bin/env python3
"""Ensure Claude cache proxy stays up on boot — NO upstream chat/probe (no quota burn)."""

from __future__ import annotations

from pathlib import Path

import paramiko

from scripts.deploy_common import configure_ssh_host_keys

HOST = "117.72.118.95"


def password() -> str:
    for line in Path(r"D:\Downloads\VPS.txt").read_text(encoding="utf-8").splitlines():
        if HOST in line and "\u5bc6\u7801" in line:
            for sep in ("\u5bc6\u7801\uff1a", "\u5bc6\u7801:"):
                if sep in line:
                    return line.split(sep, 1)[-1].strip()
    raise SystemExit("no pw")


def main() -> int:
    c = paramiko.SSHClient()
    configure_ssh_host_keys(c)
    c.connect(HOST, username="root", password=password(), timeout=20, allow_agent=False, look_for_keys=False)
    # Only systemd + nginx static checks — never curl chat/completions
    cmd = r"""
set -e
systemctl enable claude-cache-proxy.service
systemctl is-enabled claude-cache-proxy.service
systemctl is-active claude-cache-proxy.service
# nginx must route Claude chat to :3001 (no request sent)
grep -n 'location = /v1/chat/completions' /etc/nginx/sites-enabled/newapi-managed
grep -A3 'location = /v1/chat/completions' /etc/nginx/sites-enabled/newapi-managed | grep -q '3001'
grep -n 'location = /v1/messages' /etc/nginx/sites-enabled/newapi-managed
echo CONFIG_OK
"""
    _, o, e = c.exec_command(cmd, timeout=40)
    print(o.read().decode("utf-8", "replace").encode("ascii", "replace").decode())
    err = e.read().decode("utf-8", "replace")
    if err.strip():
        print(err.encode("ascii", "replace").decode()[:400])
    code = o.channel.recv_exit_status()
    c.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
