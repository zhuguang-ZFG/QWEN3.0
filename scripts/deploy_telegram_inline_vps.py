#!/usr/bin/env python3
"""Deploy TG-10.0-3 Telegram inline mode to VPS."""

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
    "telegram_inline.py",
    "telegram_bot.py",
    "routes/telegram.py",
]


def _run(ssh: paramiko.SSHClient, cmd: str) -> str:
    _stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)
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

    _ensure_env(ssh, "TELEGRAM_INLINE_ENABLED", "1")
    print("env TELEGRAM_INLINE_ENABLED=1")

    _run(ssh, "systemctl restart lima-router")
    time.sleep(8)
    active = _run(ssh, "systemctl is-active lima-router")
    verify = _run(
        ssh,
        f"cd {REMOTE} && set -a && . ./.env 2>/dev/null; set +a; "
        "/usr/local/bin/python3.10 -c "
        "\"from telegram_inline import inline_enabled; print(inline_enabled())\" 2>/dev/null",
    ).splitlines()[0].strip()
    print(f"service={active} inline_enabled={verify}")
    ok = active.strip() == "active" and verify.strip() == "True"
    print("deploy_telegram_inline_ok" if ok else "deploy_telegram_inline_FAILED")
    ssh.close()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
