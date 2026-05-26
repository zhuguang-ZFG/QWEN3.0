#!/usr/bin/env python3
"""Check if Netdata kickstart is still running on VPS."""

from __future__ import annotations

import os
import sys

import paramiko

SERVER = "47.112.162.80"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)
    cmds = [
        "pgrep -af kickstart || echo no_kickstart",
        "pgrep -af netdata || echo no_netdata_proc",
        "test -f /tmp/netdata-kickstart.sh && wc -c /tmp/netdata-kickstart.sh || echo no_script",
        "systemctl is-active netdata 2>/dev/null || echo inactive",
    ]
    for cmd in cmds:
        _i, o, _e = ssh.exec_command(cmd, timeout=20)
        print(f"$ {cmd}\n{o.read().decode().strip()}\n")
    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
