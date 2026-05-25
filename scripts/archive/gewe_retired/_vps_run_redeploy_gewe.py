#!/usr/bin/env python3
"""Upload and run official gewe redeploy on VPS."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import paramiko

SERVER = os.environ.get("LIMA_VPS_HOST", "47.112.162.80")
REMOTE = "/opt/lima-router"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))


def main() -> None:
    base = Path(__file__).resolve().parent.parent
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)
    sftp = ssh.open_sftp()
    sftp.put(str(base / "scripts/_vps_redeploy_gewe_official.sh"), f"{REMOTE}/_vps_redeploy_gewe_official.sh")
    sftp.close()
    _i, o, e = ssh.exec_command(
        f"chmod +x {REMOTE}/_vps_redeploy_gewe_official.sh && bash {REMOTE}/_vps_redeploy_gewe_official.sh",
        timeout=600,
    )
    out = (o.read() + e.read()).decode("utf-8", errors="replace")
    print(out)
    ssh.close()
    if "done" not in out:
        sys.exit(1)


if __name__ == "__main__":
    main()
