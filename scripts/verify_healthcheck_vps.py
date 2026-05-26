#!/usr/bin/env python3
"""Verify VPS healthcheck cron after deploy."""
from __future__ import annotations

import os
import sys

import paramiko

SERVER = "47.112.162.80"
REMOTE = "/opt/lima-router"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)

    def run(cmd: str) -> str:
        _stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)
        return (stdout.read() + stderr.read()).decode("utf-8", errors="replace").strip()

    print(run(f"chmod +x {REMOTE}/scripts/vps_router_healthcheck.sh"))
    print("env:", run(f"grep HEALTHCHECK_LIMA_VPS_URL {REMOTE}/.env | cut -c1-40"))
    print("enabled:", run(f"grep LIMA_HEALTHCHECK_ENABLED {REMOTE}/.env"))
    print("cron:", run("cat /etc/cron.d/lima-router-healthcheck"))
    exit_code = run(
        f"cd {REMOTE} && set -a && . ./.env && set +a && "
        f"LIMA_HEALTHCHECK_ENABLED=1 ./scripts/vps_router_healthcheck.sh; echo exit=$?"
    )
    print("cron_run:", exit_code)
    print("log:", run("tail -5 /var/log/lima-healthcheck.log 2>/dev/null || echo no-log"))
    ssh.close()
    ok = "exit=0" in exit_code or "exit=0" in exit_code.replace("\n", " ")
    print("verify_healthcheck_vps_ok" if ok else "verify_healthcheck_vps_FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
