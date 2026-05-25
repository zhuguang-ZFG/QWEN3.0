#!/usr/bin/env python3
"""Patch VPS env + generate Gewechat login QR on sidecar."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import paramiko

SERVER = "47.112.162.80"
REMOTE = "/opt/lima-router"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))


def main() -> None:
    base = Path(__file__).resolve().parent.parent
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)
    sftp = ssh.open_sftp()
    sftp.put(str(base / "scripts/_patch_sidecar_env_remote.py"), f"{REMOTE}/_patch_sidecar_env.py")
    sftp.put(str(base / "scripts/_vps_refresh_qr_remote.py"), f"{REMOTE}/_vps_refresh_qr.py")
    sftp.put(str(base / "scripts/_vps_gewe_bootstrap.sh"), f"{REMOTE}/_vps_gewe_bootstrap.sh")
    sftp.put(str(base / "wechat_bridge/gewechat_client.py"), f"{REMOTE}/wechat_bridge/gewechat_client.py")
    sftp.close()

    def run(cmd: str, *, timeout: int = 600) -> str:
        _i, o, e = ssh.exec_command(cmd, timeout=timeout)
        return (o.read() + e.read()).decode("utf-8", errors="replace")

    print(run(f"cd {REMOTE} && /usr/local/bin/python3.10 _patch_sidecar_env.py"))
    print(run("systemctl restart lima-wechat-sidecar"))
    time.sleep(2)
    out = run(f"cd {REMOTE} && /usr/local/bin/python3.10 _vps_refresh_qr.py")
    print(out)
    ssh.close()
    if "qr_ok" not in out:
        sys.exit(1)
    print(f"\nOpen QR: http://{SERVER}:9919/login-qr")


if __name__ == "__main__":
    main()
