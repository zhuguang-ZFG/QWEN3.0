#!/usr/bin/env python3
"""Deploy five-line closeout slice: CF-G-3 routing + TG-GH-4 Telegram commands."""

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
    "router_v3.py",
    "backends_constants.py",
    "telegram_operator_tools.py",
    "routes/telegram.py",
    "routes/telegram_commands.py",
]


def _run(ssh: paramiko.SSHClient, cmd: str, timeout: float | None = 60) -> str:
    _stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        out = (out + "\n" + err).strip()
    return out


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
            ssh.close()
            sys.exit(f"missing {local}")
        sftp = ssh.open_sftp()
        remote = f"{REMOTE}/{rel.replace(chr(92), '/')}"
        sftp.put(str(local), remote)
        sftp.close()
        print(f"uploaded {rel}")

    _run(ssh, "systemctl restart lima-router")
    time.sleep(8)

    verify = _run(
        ssh,
        f"cd {REMOTE} && /usr/local/bin/python3.10 -c "
        f"\"import router_v3; print(router_v3.POOLS['chat_fast']['strong'][0])\"",
    )
    print("chat_fast_strong_0:", verify.strip())
    active = _run(ssh, "systemctl is-active lima-router").strip()
    ssh.close()
    ok = active == "active" and "google_flash_lite" in verify
    print("deploy_five_line_closeout_ok" if ok else "deploy_five_line_closeout_FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
