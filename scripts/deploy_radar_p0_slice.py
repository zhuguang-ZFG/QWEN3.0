#!/usr/bin/env python3
"""Deploy radar P0 slice: gitee search + LC-W-1e smoke deps."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import paramiko

from deploy_common import KEY, REMOTE, SERVER, notify_deploy_success, notify_smoke_success

FILES = [
    "search_gateway/gitee_tools.py",
    "search_gateway/safety.py",
    "agent_contracts/task_contract.py",
    "agent_evolution/__init__.py",
    "agent_evolution/candidates.py",
    "agent_evolution/promote.py",
    "agent_runtime/prompt_contract.py",
    "routes/agent_task_store.py",
    "routes/agent_task_evolution.py",
    "routes/agent_task_schemas.py",
    "routes/agent_task_service.py",
    "routes/agent_tasks.py",
    "scripts/smoke_lcw1_prompt_contract_e2e.py",
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
    _run(ssh, f"mkdir -p {REMOTE}/search_gateway {REMOTE}/agent_evolution {REMOTE}/agent_contracts {REMOTE}/agent_runtime {REMOTE}/routes {REMOTE}/scripts")
    for rel in FILES:
        local = base / rel
        remote = f"{REMOTE}/{rel.replace(chr(92), '/')}"
        sftp.put(str(local), remote)
        print(f"uploaded {rel}")
    sftp.close()

    _run(ssh, "systemctl restart lima-router", timeout=60)
    time.sleep(3)

    smoke_cmd = (
        f"cd {REMOTE} && set -a && . ./.env && set +a && "
        "/usr/local/bin/python3.10 scripts/smoke_lcw1_prompt_contract_e2e.py"
    )
    code, smoke_out = _run(ssh, smoke_cmd, timeout=90)
    print(smoke_out)

    _, health = _run(ssh, "curl -sf http://127.0.0.1:8080/health", timeout=30)

    ok = code == 0 and "smoke_ok" in smoke_out and bool(health)
    notify_deploy_success(ssh, "radar-P0", service="lima-router", health=health[:160])
    if ok:
        notify_smoke_success(ssh, "LC-W-1e prompt contract", detail=smoke_out[:200])
    ssh.close()
    print("deploy_radar_p0_ok" if ok else "deploy_radar_p0_fail")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
