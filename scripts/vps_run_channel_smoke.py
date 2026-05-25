#!/usr/bin/env python3
"""VPS smoke for /channel/v1/wechat (tools + auto guest bind)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import paramiko

SERVER = "47.112.162.80"
REMOTE = "/opt/lima-router"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))


def main() -> None:
    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, banner_timeout=30, timeout=60)

    base = Path(__file__).resolve().parent
    smoke_local = base / "_vps_channel_smoke_remote.py"
    sftp = ssh.open_sftp()
    sftp.put(str(smoke_local), f"{REMOTE}/_vps_channel_smoke.py")
    sftp.close()

    cmd = f"cd {REMOTE} && /usr/local/bin/python3.10 _vps_channel_smoke.py"
    _stdin, stdout, stderr = ssh.exec_command(cmd, timeout=120)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    ssh.close()

    print(out, end="")
    if err.strip():
        print(err, file=sys.stderr)
    if code != 0:
        sys.exit(code)
    if "channel_smoke_passed" not in out:
        sys.exit("channel smoke did not report success")


if __name__ == "__main__":
    main()
