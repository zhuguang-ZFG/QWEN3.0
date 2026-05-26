#!/usr/bin/env python3
"""Deploy P2-25: eval topology via FRP/8088 for local-proxy backends."""

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
    "eval_topology.py",
    "eval_call.py",
    "eval_status.py",
    "routes/eval_internal.py",
    "routes/route_registry.py",
    "scripts/eval_coding_backends.py",
    "scripts/run_radar_eval_slice.py",
]

ENV_LINES = [
    "LIMA_EVAL_TOPOLOGY=1",
    "LIMA_EVAL_VIA_ROUTER_URL=http://127.0.0.1:8088",
]


def _ensure_env(ssh: paramiko.SSHClient) -> None:
    for line in ENV_LINES:
        key = line.split("=", 1)[0]
        cmd = (
            f"grep -q '^{key}=' {REMOTE}/.env 2>/dev/null || "
            f"echo '{line}' >> {REMOTE}/.env"
        )
        ssh.exec_command(cmd)
        print(f"env {key}")


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
            sys.exit(f"missing local file: {local}")
        remote = f"{REMOTE}/{rel.replace(chr(92), '/')}"
        remote_dir = os.path.dirname(remote)
        ssh.exec_command(f"mkdir -p {remote_dir}")
        sftp = ssh.open_sftp()
        sftp.put(str(local), remote)
        sftp.close()
        print(f"uploaded {rel}")

    _ensure_env(ssh)
    ssh.exec_command("systemctl restart lima-router")
    time.sleep(8)
    _i, o, _e = ssh.exec_command("systemctl is-active lima-router")
    print("service", o.read().decode().strip())
    _i, o, _e = ssh.exec_command(
        "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8088/health"
    )
    print("frp8088_health", o.read().decode().strip())
    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
