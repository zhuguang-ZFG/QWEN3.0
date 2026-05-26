#!/usr/bin/env python3
"""Probe VPS for Netdata agent / MCP readiness (PE-C-1)."""

from __future__ import annotations

import os
import sys

import paramiko

SERVER = "47.112.162.80"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))


def main() -> int:
    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)

    cmds = [
        "which netdata 2>/dev/null || echo missing",
        "netdata -v 2>/dev/null | head -1 || true",
        "systemctl is-active netdata 2>/dev/null || echo inactive",
        "curl -sf http://127.0.0.1:19999/api/v1/info 2>/dev/null | head -c 180 || echo no_api",
        "curl -sf -o /dev/null -w '%{http_code}' http://127.0.0.1:19999/mcp 2>/dev/null || echo mcp_fail",
    ]
    for cmd in cmds:
        _stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
        out = stdout.read().decode("utf-8", errors="replace").strip()
        err = stderr.read().decode("utf-8", errors="replace").strip()
        print(f"$ {cmd}\n{out or err}\n")

    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
