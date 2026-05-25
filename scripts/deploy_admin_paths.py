#!/usr/bin/env python3
"""Deploy admin path fixes to LiMa VPS."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import paramiko

SERVER = "47.112.162.80"
REMOTE = "/opt/lima-router"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))
FILES = [
    "routes/admin_state.py",
    "routes/admin_api.py",
    "routes/request_tracking.py",
]


def main() -> None:
    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    base = Path(__file__).resolve().parent.parent
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, banner_timeout=30, timeout=60)

    sftp = ssh.open_sftp()
    for rel in FILES:
        sftp.put(str(base / rel), f"{REMOTE}/{rel}")
        print(f"uploaded {rel}", flush=True)
    sftp.close()

    cmd = (
        "cd /opt/lima-router && /usr/local/bin/python3.10 -c "
        "'from routes.admin_state import FALLBACK_LOG; "
        "from routes.admin_api import REPO_ROOT; "
        "print(FALLBACK_LOG); print(REPO_ROOT)'"
    )
    _stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    print(out, flush=True)
    if err and "Traceback" in err:
        print(err, flush=True)
        sys.exit(1)
    if "/opt/lima-router" not in out:
        sys.exit("unexpected VPS path output")
    ssh.close()


if __name__ == "__main__":
    main()
