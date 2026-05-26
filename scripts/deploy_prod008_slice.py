#!/usr/bin/env python3
"""Deploy PROD-008 learning loop E2E smoke slice."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import paramiko

from deploy_common import KEY, REMOTE, SERVER, notify_deploy_success, notify_smoke_success

FILES = [
    "scripts/smoke_prod008_learning_loop_e2e.py",
    "routes/ops_metrics.py",
    "session_memory/learning_loop.py",
]


def _run(ssh: paramiko.SSHClient, cmd: str, timeout: float = 120) -> tuple[int, str]:
    _i, o, e = ssh.exec_command(cmd, timeout=timeout)
    out = (o.read() + e.read()).decode("utf-8", errors="replace").strip()
    return o.channel.recv_exit_status(), out


def main() -> int:
    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    base = Path(__file__).resolve().parent.parent
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)

    sftp = ssh.open_sftp()
    _run(ssh, f"mkdir -p {REMOTE}/scripts {REMOTE}/routes {REMOTE}/session_memory")
    for rel in FILES:
        remote = f"{REMOTE}/{rel.replace(chr(92), '/')}"
        sftp.put(str(base / rel), remote)
        print(f"uploaded {rel}")
    sftp.close()

    _run(ssh, "systemctl restart lima-router", timeout=60)
    time.sleep(3)

    smoke_cmd = (
        f"cd {REMOTE} && set -a && . ./.env && set +a && "
        "/usr/local/bin/python3.10 scripts/smoke_prod008_learning_loop_e2e.py"
    )
    code, smoke_out = _run(ssh, smoke_cmd, timeout=90)
    print(smoke_out)

    _, health = _run(ssh, "curl -sf http://127.0.0.1:8080/health", timeout=30)
    smoke_ok = False
    try:
        payload = json.loads(smoke_out.splitlines()[-1])
        smoke_ok = payload.get("smoke_ok") is True
    except (json.JSONDecodeError, IndexError):
        smoke_ok = "smoke_ok" in smoke_out and "true" in smoke_out
    ok = code == 0 and smoke_ok and bool(health)
    notify_deploy_success(ssh, "PROD-008", service="lima-router", health=health[:160])
    if ok:
        notify_smoke_success(ssh, "PROD-008 learning loop", detail=smoke_out[:220])
    ssh.close()
    print("deploy_prod008_ok" if ok else "deploy_prod008_fail")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
