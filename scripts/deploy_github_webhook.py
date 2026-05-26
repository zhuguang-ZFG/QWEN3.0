#!/usr/bin/env python3
"""Deploy CQ-GH-001 GitHub webhook integration to LiMa VPS."""

from __future__ import annotations

import os
import secrets
import sys
import time
from pathlib import Path

import paramiko

SERVER = "47.112.162.80"
REMOTE = "/opt/lima-router"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))
ENV_FILE = f"{REMOTE}/.env"

FILES = [
    "github_webhook/__init__.py",
    "github_webhook/verify.py",
    "github_webhook/format.py",
    "github_webhook/activity.py",
    "github_webhook/auto_task.py",
    "routes/github_webhook.py",
    "routes/route_registry.py",
    "telegram_notify.py",
    "webhook_activity_buffer.py",
]

ENV_KEYS = {
    "GITHUB_WEBHOOK_ENABLED": "1",
    "GITHUB_WEBHOOK_REPOS": "zhuguang-ZFG/QWEN3.0",
}


def _run(ssh: paramiko.SSHClient, cmd: str, timeout: float | None = None) -> str:
    _stdin, stdout, stderr = ssh.exec_command(cmd)
    if timeout is not None:
        stdout.channel.settimeout(timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        out = (out + "\n" + err).strip()
    return out


def _log(msg: str) -> None:
    print(msg, flush=True)


def _ensure_remote_dir(sftp: paramiko.SFTPClient, remote_path: str) -> None:
    parts = remote_path.replace("\\", "/").split("/")
    cur = ""
    for part in parts[:-1]:
        if not part:
            continue
        cur = f"{cur}/{part}" if cur else part
        try:
            sftp.stat(cur)
        except OSError:
            sftp.mkdir(cur)


def _upsert_env(ssh: paramiko.SSHClient, key: str, value: str) -> None:
    escaped = value.replace("'", "'\"'\"'")
    cmd = (
        f"grep -q '^{key}=' {ENV_FILE} 2>/dev/null && "
        f"sed -i 's|^{key}=.*|{key}={escaped}|' {ENV_FILE} || "
        f"echo '{key}={escaped}' >> {ENV_FILE}"
    )
    _run(ssh, cmd)


def _restart_router(ssh: paramiko.SSHClient) -> None:
    _run(ssh, "systemctl stop lima-router 2>/dev/null || true")
    _run(ssh, "pkill -9 -f 'uvicorn server:app' || true")
    _run(ssh, "pkill -9 -f 'python3.10 server.py' || true")
    _run(ssh, "fuser -k 8080/tcp 2>/dev/null || true")
    time.sleep(3)
    _run(ssh, "systemctl reset-failed lima-router 2>/dev/null || true")
    out = _run(ssh, "systemctl start lima-router 2>&1", timeout=15)
    if out:
        _log(out[:200])
    time.sleep(8)


def main() -> int:
    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    base = Path(__file__).resolve().parent.parent
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, banner_timeout=30, timeout=60)

    _log("deploy CQ-GH-001 github webhook (no VPS backup; rollback via GitHub)")

    # Preserve existing secret or generate one
    existing = _run(ssh, f"grep '^GITHUB_WEBHOOK_SECRET=' {ENV_FILE} 2>/dev/null | head -1").strip()
    if existing and "=" in existing:
        secret = existing.split("=", 1)[1]
        _log("reuse GITHUB_WEBHOOK_SECRET from .env")
    else:
        secret = secrets.token_hex(24)
        _log(f"generated GITHUB_WEBHOOK_SECRET (stored on VPS only): {secret[:8]}...")

    for key, value in ENV_KEYS.items():
        _upsert_env(ssh, key, value)
    _upsert_env(ssh, "GITHUB_WEBHOOK_SECRET", secret)

    _run(ssh, f"mkdir -p {REMOTE}/github_webhook {REMOTE}/routes")

    sftp = ssh.open_sftp()
    for rel in FILES:
        local = base / rel
        if not local.is_file():
            sftp.close()
            ssh.close()
            sys.exit(f"missing local file: {local}")
        remote = f"{REMOTE}/{rel.replace(chr(92), '/')}"
        sftp.put(str(local), remote)
        _log(f"uploaded {rel} ({local.stat().st_size} bytes)")
    sftp.close()

    _restart_router(ssh)

    active = _run(ssh, "systemctl is-active lima-router 2>/dev/null").strip()
    disabled = _run(
        ssh,
        "curl -s -o /dev/null -w '%{http_code}' -X POST http://127.0.0.1:8080/github/webhook -d '{}'",
    ).strip()
    health = _run(ssh, "curl -sf http://127.0.0.1:8080/health | head -c 120")

    _log(f"service={active}")
    _log(f"github_webhook_disabled_probe={disabled} (expect 503 before enabled reload)")
    _log(f"health={health}")

    # Re-read env after restart (systemd loads lima.env)
    probe = _run(
        ssh,
        "curl -s -o /dev/null -w '%{http_code}' -X POST http://127.0.0.1:8080/github/webhook "
        "-H 'Content-Type: application/json' -d '{\"zen\":\"ping\"}'",
    ).strip()
    _log(f"github_webhook_post_restart={probe} (expect 403 without signature when enabled)")

    ok = active == "active" and probe in {"403", "503"}
    if not ok:
        _log(_run(ssh, "journalctl -u lima-router -n 15 --no-pager"))
        ssh.close()
        return 1

    _log("deploy_github_webhook_ok")
    _log("GITHUB_WEBHOOK_SECRET for GitHub UI setup (copy from VPS lima.env if needed)")
    _log(f"secret_prefix={secret[:12]}...")
    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
