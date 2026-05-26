#!/usr/bin/env python3
"""Deploy TG-10.0-2 Bot-to-Bot handler to VPS."""

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
    "telegram_b2b.py",
    "telegram_notify.py",
    "routes/telegram.py",
]

CODE_BOT_USER = os.environ.get("TELEGRAM_CODE_BOT_USERNAMES", "lima_code_bot")


def _run(ssh: paramiko.SSHClient, cmd: str, timeout: float = 60) -> str:
    _stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return (stdout.read() + stderr.read()).decode("utf-8", errors="replace").strip()


def _ensure_env(ssh: paramiko.SSHClient, key: str, value: str) -> None:
    _run(
        ssh,
        f"grep -q '^{key}=' {REMOTE}/.env 2>/dev/null && "
        f"sed -i 's|^{key}=.*|{key}={value}|' {REMOTE}/.env || "
        f"echo '{key}={value}' >> {REMOTE}/.env",
    )


def main() -> int:
    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    base = Path(__file__).resolve().parents[1]
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)

    for rel in FILES:
        sftp = ssh.open_sftp()
        sftp.put(str(base / rel), f"{REMOTE}/{rel.replace(chr(92), '/')}")
        sftp.close()
        print(f"uploaded {rel}")

    _ensure_env(ssh, "TELEGRAM_B2B_ENABLED", "1")
    _ensure_env(ssh, "TELEGRAM_CODE_BOT_USERNAMES", CODE_BOT_USER)
    print(f"env TELEGRAM_B2B_ENABLED=1 TELEGRAM_CODE_BOT_USERNAMES={CODE_BOT_USER}")

    _run(ssh, "systemctl restart lima-router")
    time.sleep(8)
    active = _run(ssh, "systemctl is-active lima-router")
    verify = _run(
        ssh,
        f"cd {REMOTE} && set -a && . ./.env 2>/dev/null; set +a; "
        "/usr/local/bin/python3.10 -c "
        "\"from telegram_b2b import b2b_enabled; print(b2b_enabled())\"",
    )
    print(f"service={active} b2b_enabled={verify}")
    ok = active.strip() == "active" and verify.strip() == "True"
    print("deploy_telegram_b2b_ok" if ok else "deploy_telegram_b2b_FAILED")
    ssh.close()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
