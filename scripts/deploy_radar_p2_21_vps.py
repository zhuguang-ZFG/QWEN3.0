#!/usr/bin/env python3
"""Deploy radar P2-21: OldLLM sync + ops Apprise alerts."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import paramiko

SERVER = "47.112.162.80"
REMOTE = "/opt/lima-router"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))

FILES = [
    "oldllm_sync.py",
    "oldllm_diag.py",
    "notify/ops_alerts.py",
    "notify/apprise_bridge.py",
    "notify/__init__.py",
    "routes/telegram_diag_tools.py",
    "routes/telegram_quick_menu.py",
    "routes/telegram.py",
    "docs/LC_W_APPRISE_NOTIFY.md",
]


def main() -> int:
    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    base = Path(__file__).resolve().parent.parent
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)

    for rel in FILES:
        local = base / rel
        if not local.is_file():
            sys.exit(f"missing local file: {local}")
        remote = f"{REMOTE}/{rel.replace(chr(92), '/')}"
        remote_dir = os.path.dirname(remote)
        ssh.exec_command(f"mkdir -p {remote_dir}")
        sftp = ssh.open_sftp()
        sftp.put(str(local), remote)
        sftp.close()
        print(f"uploaded {rel}")

    ssh.exec_command("systemctl restart lima-router")
    time.sleep(8)
    _i, o, _e = ssh.exec_command("systemctl is-active lima-router")
    print("service", o.read().decode().strip())
    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
