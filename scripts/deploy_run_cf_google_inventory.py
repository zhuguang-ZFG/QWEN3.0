#!/usr/bin/env python3
"""Run CF-G-0 inventory on VPS using /opt/lima-router/.env credentials."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import paramiko

SERVER = "47.112.162.80"
REMOTE = "/opt/lima-router"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))

FILES = [
    "provider_inventory/__init__.py",
    "provider_inventory/cloudflare.py",
    "provider_inventory/google.py",
    "provider_inventory/compare.py",
    "provider_inventory/weekly_diff.py",
    "telegram_digest.py",
    "scripts/run_cf_google_inventory.py",
    "scripts/inventory_cloudflare_models.py",
    "scripts/inventory_google_models.py",
]


def _run(ssh: paramiko.SSHClient, cmd: str, timeout: float = 120) -> tuple[int, str]:
    _i, o, e = ssh.exec_command(cmd, timeout=timeout)
    out = (o.read() + e.read()).decode("utf-8", "replace")
    code = o.channel.recv_exit_status()
    return code, out.strip()


def main() -> int:
    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    base = Path(__file__).resolve().parent.parent
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, banner_timeout=30, timeout=60)

    sftp = ssh.open_sftp()
    _run(ssh, f"mkdir -p {REMOTE}/provider_inventory {REMOTE}/scripts {REMOTE}/data {REMOTE}/docs")
    for rel in FILES:
        local = base / rel
        remote = f"{REMOTE}/{rel.replace(chr(92), '/')}"
        sftp.put(str(local), remote)
    sftp.close()

    cmd = (
        f"cd {REMOTE} && set -a && . ./.env && set +a && "
        f"/usr/local/bin/python3.10 scripts/run_cf_google_inventory.py"
    )
    code, out = _run(ssh, cmd, timeout=600)
    print(out)

    for rel in ("data/cf_model_inventory.json", "data/google_model_inventory.json", "docs/CF_GOOGLE_INVENTORY_REPORT.md"):
        remote = f"{REMOTE}/{rel}"
        local = base / rel
        local.parent.mkdir(parents=True, exist_ok=True)
        try:
            sftp = ssh.open_sftp()
            sftp.get(remote, str(local))
            sftp.close()
            print(f"pulled {rel}")
        except OSError as exc:
            print(f"warn: could not pull {rel}: {exc}")

    ssh.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
