#!/usr/bin/env python3
"""Deploy GI-G-2 Gitee webhook integration to LiMa VPS."""

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
    "gitee_webhook/__init__.py",
    "gitee_webhook/verify.py",
    "gitee_webhook/format.py",
    "gitee_webhook/dedupe.py",
    "github_webhook/format.py",
    "routes/gitee_webhook.py",
    "routes/github_webhook.py",
    "routes/route_registry.py",
    "telegram_notify.py",
    "scripts/notify_ops_telegram.py",
]

ENV_KEYS = {
    "GITEE_WEBHOOK_ENABLED": "1",
    "GITEE_WEBHOOK_REPOS": "zhuguang-cn/QWEN3.0",
    "GITEE_WEBHOOK_DEDUPE_GITHUB": "1",
}


def _run(ssh: paramiko.SSHClient, cmd: str, timeout: float | None = None) -> str:
    _stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        out = (out + "\n" + err).strip()
    return out


def _log(msg: str) -> None:
    print(msg, flush=True)


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
    _run(ssh, "systemctl start lima-router 2>&1", timeout=15)
    time.sleep(8)


def main() -> int:
    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    base = Path(__file__).resolve().parent.parent
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, banner_timeout=30, timeout=60)

    _log("deploy GI-G-2 gitee webhook")

    existing = _run(ssh, f"grep '^GITEE_WEBHOOK_SECRET=' {ENV_FILE} 2>/dev/null | head -1").strip()
    if existing and "=" in existing:
        secret = existing.split("=", 1)[1]
        _log("reuse GITEE_WEBHOOK_SECRET from .env")
    else:
        secret = secrets.token_hex(24)
        _log(f"generated GITEE_WEBHOOK_SECRET prefix={secret[:8]}...")

    for key, value in ENV_KEYS.items():
        _upsert_env(ssh, key, value)
    _upsert_env(ssh, "GITEE_WEBHOOK_SECRET", secret)

    _run(ssh, f"mkdir -p {REMOTE}/gitee_webhook {REMOTE}/routes {REMOTE}/data {REMOTE}/scripts")

    sftp = ssh.open_sftp()
    for rel in FILES:
        local = base / rel
        if not local.is_file():
            sftp.close()
            ssh.close()
            sys.exit(f"missing local file: {local}")
        remote = f"{REMOTE}/{rel.replace(chr(92), '/')}"
        sftp.put(str(local), remote)
        _log(f"uploaded {rel}")
    sftp.close()

    _restart_router(ssh)

    active = _run(ssh, "systemctl is-active lima-router 2>/dev/null").strip()
    probe = _run(
        ssh,
        "curl -s -o /dev/null -w '%{http_code}' -X POST http://127.0.0.1:8080/gitee/webhook "
        "-H 'Content-Type: application/json' -d '{\"hook_name\":\"push_hooks\"}'",
    ).strip()
    health = _run(ssh, "curl -sf http://127.0.0.1:8080/health | head -c 200")

    _log(f"service={active}")
    _log(f"gitee_webhook_probe={probe} (expect 403 without token)")
    _log(f"health={health}")

    ok = active == "active" and probe in {"403", "503"}
    if ok:
        _log("deploy_gitee_webhook_ok")
        _log(f"Configure Gitee UI password = GITEE_WEBHOOK_SECRET (prefix {secret[:12]}...)")
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import deploy_common

        deploy_common.notify_deploy_success(
            ssh, "gitee_webhook", service=active, health=health,
        )
    else:
        _log(_run(ssh, "journalctl -u lima-router -n 15 --no-pager"))

    ssh.close()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
