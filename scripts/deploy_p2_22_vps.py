#!/usr/bin/env python3
"""Deploy P2-22: OldLLM FRP tunnel env + eval quiet + auto archive."""

from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

import paramiko

SERVER = "47.112.162.80"
REMOTE = "/opt/lima-router"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))
ENV_LINE = "OLDLLM_REFRESH_URL=http://127.0.0.1:4501"

FILES = [
    "eval_quiet.py",
    "telegram_notify.py",
    "oldllm_sync.py",
    "routes/telegram_eval_tools.py",
    "routes/telegram_diag_tools.py",
    "scripts/smoke_oldllm_refresh_tunnel.py",
]


def _patch_env(ssh: paramiko.SSHClient) -> None:
    env_path = f"{REMOTE}/.env"
    _i, o, _e = ssh.exec_command(f"test -f {env_path} && cat {env_path} || true")
    text = o.read().decode("utf-8", errors="replace")
    if "OLDLLM_REFRESH_URL=" in text:
        print("OLDLLM_REFRESH_URL already in .env")
        return
    ssh.exec_command(f"grep -q OLDLLM_REFRESH_URL {env_path} 2>/dev/null || echo '{ENV_LINE}' >> {env_path}")
    print(f"appended {ENV_LINE} to .env")


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

    _patch_env(ssh)
    ssh.exec_command("systemctl restart lima-router")
    time.sleep(8)
    _i, o, _e = ssh.exec_command("systemctl is-active lima-router")
    print("service", o.read().decode().strip())

    _i, o, e = ssh.exec_command(
        f"cd {REMOTE} && /usr/local/bin/python3.10 scripts/smoke_oldllm_refresh_tunnel.py 2>&1"
    )
    smoke = (o.read() + e.read()).decode("utf-8", errors="replace").strip()
    print("smoke", smoke[-400:] if len(smoke) > 400 else smoke)
    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
