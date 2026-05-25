#!/usr/bin/env python3
"""Remove all LiMa VPS runtime backups (rollback via GitHub)."""

from __future__ import annotations

import os
import sys

import paramiko

SERVER = "47.112.162.80"
REMOTE = "/opt/lima-router/backups"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))


def main() -> int:
    if not os.path.isfile(KEY):
        print(f"SSH key not found: {KEY}", file=sys.stderr)
        return 1

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, banner_timeout=30, timeout=120)

    cmds = [
        f"du -sh {REMOTE} 2>/dev/null || echo '0 backups'",
        f"rm -rf {REMOTE}/* {REMOTE}/.[!.]* 2>/dev/null; mkdir -p {REMOTE}",
        f"du -sh {REMOTE}",
        "df -h / | tail -1",
    ]
    for cmd in cmds:
        _stdin, stdout, stderr = ssh.exec_command(cmd, timeout=180)
        out = stdout.read().decode("utf-8", errors="replace").strip()
        err = stderr.read().decode("utf-8", errors="replace").strip()
        print(out or err)

    ssh.close()
    print("cleanup_token vps_backups_cleared", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
