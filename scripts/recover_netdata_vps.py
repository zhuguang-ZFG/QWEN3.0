#!/usr/bin/env python3
"""Recover Netdata after failed restart (stale PID / lock)."""

from __future__ import annotations

import os
import sys
import time

import paramiko

SERVER = "47.112.162.80"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))


def _run(ssh: paramiko.SSHClient, cmd: str, timeout: float = 120) -> tuple[int, str]:
    _stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = (stdout.read() + stderr.read()).decode("utf-8", errors="replace").strip()
    code = stdout.channel.recv_exit_status()
    return code, out


def main() -> int:
    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)

    steps = [
        "systemctl stop netdata 2>/dev/null || true",
        "pkill -9 netdata 2>/dev/null || true",
        "rm -f /run/netdata/netdata.pid /run/netdata/netdata.lock 2>/dev/null || true",
        "sleep 2",
        "systemctl start netdata",
        "sleep 4",
        "systemctl is-active netdata",
        "ss -tlnp 2>/dev/null | grep 19999 || true",
        "curl -sf http://127.0.0.1:19999/api/v1/info | head -c 120 || true",
    ]
    for cmd in steps:
        code, out = _run(ssh, cmd, timeout=180)
        print(f"$ {cmd}")
        print(out[:400] or f"(exit {code})")

    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
