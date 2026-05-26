#!/usr/bin/env python3
"""Deploy TG-GH-3 unified digest + webhook activity buffer."""

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
    "webhook_activity_buffer.py",
    "telegram_digest.py",
    "telegram_notify.py",
    "github_webhook/activity.py",
    "gitee_webhook/activity.py",
    "routes/github_webhook.py",
    "routes/gitee_webhook.py",
    "routes/telegram.py",
    "scripts/notify_ops_telegram.py",
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
    _run(ssh, f"mkdir -p {REMOTE}/scripts")

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
        f"cd {REMOTE} && set -a && . ./.env && set +a && "
        f"/usr/local/bin/python3.10 -c \"import asyncio; "
        f"from telegram_digest import build_unified_digest_text; "
        f"print(build_unified_digest_text()[:120])\"",
    )
    print("digest_preview:", verify.replace("\n", " | "))
    active = _run(ssh, "systemctl is-active lima-router").strip()
    ok = active == "active"
    if ok:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import deploy_common

        deploy_common.notify_deploy_success(
            ssh, "telegram_digest", service=active, detail=verify.replace("\n", " | ")[:160],
        )
    ssh.close()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
