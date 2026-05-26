#!/usr/bin/env python3
"""Deploy TG-10.0-1 Telegram draft streaming to VPS."""

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
    "telegram_draft_stream.py",
    "routes/telegram_chat_stream.py",
    "routes/telegram_commands.py",
    "routes/stream_handlers.py",
    "streaming.py",
    "streaming_bridge.py",
]


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
    _run(ssh, f"mkdir -p {REMOTE}/routes")

    for rel in FILES:
        local = base / rel
        sftp = ssh.open_sftp()
        sftp.put(str(local), f"{REMOTE}/{rel.replace(chr(92), '/')}")
        sftp.close()
        print(f"uploaded {rel}")

    _ensure_env(ssh, "TELEGRAM_STREAM_CHAT", "1")
    print("env TELEGRAM_STREAM_CHAT=1")

    _run(ssh, "systemctl restart lima-router")
    time.sleep(8)
    active = _run(ssh, "systemctl is-active lima-router")
    verify = _run(
        ssh,
        f"cd {REMOTE} && /usr/local/bin/python3.10 -c "
        "\"from telegram_draft_stream import stream_chat_enabled; print(stream_chat_enabled())\"",
    )
    print(f"service={active} stream_enabled={verify}")
    ok = active.strip() == "active" and verify.strip() == "True"
    print("deploy_telegram_stream_ok" if ok else "deploy_telegram_stream_FAILED")
    ssh.close()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
