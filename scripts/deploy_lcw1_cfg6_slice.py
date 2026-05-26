#!/usr/bin/env python3
"""Deploy LC-W-1 prompt contract + CF-G-6 Google inventory proxy slice."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import paramiko

from deploy_common import KEY, REMOTE, SERVER, notify_deploy_success

FILES = [
    "agent_runtime/prompt_contract.py",
    "agent_contracts/task_contract.py",
    "routes/agent_task_schemas.py",
    "routes/agent_task_service.py",
    "routes/agent_tasks.py",
    "provider_inventory/google.py",
]


def main() -> int:
    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    base = Path(__file__).resolve().parent.parent
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)

    sftp = ssh.open_sftp()
    for rel in FILES:
        local = base / rel
        remote = f"{REMOTE}/{rel.replace(chr(92), '/')}"
        sftp.put(str(local), remote)
        print(f"uploaded {rel}")
    sftp.close()

    _stdin, stdout, stderr = ssh.exec_command("systemctl restart lima-router", timeout=60)
    stdout.channel.recv_exit_status()
    time.sleep(3)

    _stdin, stdout, stderr = ssh.exec_command("curl -sf http://127.0.0.1:8080/health", timeout=30)
    health = (stdout.read() + stderr.read()).decode("utf-8", errors="replace").strip()

    _stdin, stdout, stderr = ssh.exec_command(
        f"grep -F 'prompt-contract-v0.1' {REMOTE}/routes/agent_tasks.py",
        timeout=30,
    )
    preflight = (stdout.read() + stderr.read()).decode("utf-8", errors="replace").strip()

    inv_cmd = (
        f"cd {REMOTE} && set -a && . ./.env && set +a && "
        "/usr/local/bin/python3.10 scripts/run_cf_google_inventory.py"
    )
    _stdin, stdout, stderr = ssh.exec_command(inv_cmd, timeout=600)
    inv_out = (stdout.read() + stderr.read()).decode("utf-8", errors="replace").strip()

    ok = bool(health) and "prompt-contract-v0.1" in preflight and "google models=35" in inv_out
    print(f"health={health[:120]}")
    print(f"preflight={preflight[:200]}")
    print(inv_out)

    notify_deploy_success(
        ssh,
        "LC-W-1 + CF-G-6",
        service="lima-router",
        health=health,
        detail="prompt-contract + google inventory via GFW_PROXY",
    )
    ssh.close()
    print("deploy_lcw1_cfg6_ok" if ok else "deploy_lcw1_cfg6_fail")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
