#!/usr/bin/env python3
"""Deploy PE-A-1 MCP registry inventory + VPS weekly cron."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import paramiko

SERVER = "47.112.162.80"
REMOTE = "/opt/lima-router"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))
CRON_FILE = "/etc/cron.d/lima-mcp-inventory"
LOG_FILE = "/var/log/lima-mcp-inventory.log"

FILES = [
    "provider_inventory/__init__.py",
    "provider_inventory/mcp_registries.py",
    "scripts/inventory_mcp_registries.py",
    "scripts/smoke_mcp_inventory_vps.py",
]


def _run(ssh: paramiko.SSHClient, cmd: str, timeout: float = 600) -> tuple[int, str]:
    _stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = (stdout.read() + stderr.read()).decode("utf-8", errors="replace").strip()
    return stdout.channel.recv_exit_status(), out


def main() -> int:
    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    base = Path(__file__).resolve().parents[1]
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)

    _run(ssh, f"mkdir -p {REMOTE}/provider_inventory {REMOTE}/scripts {REMOTE}/data")
    sftp = ssh.open_sftp()
    for rel in FILES:
        local = base / rel
        remote = f"{REMOTE}/{rel.replace(chr(92), '/')}"
        sftp.put(str(local), remote)
        print(f"uploaded {rel}")
    sftp.close()

    cron_body = (
        "# LiMa MCP registry inventory (PE-A-1 weekly)\n"
        "SHELL=/bin/bash\n"
        "0 4 * * 0 root "
        f"cd {REMOTE} && set -a && . ./.env 2>/dev/null; set +a && "
        f"/usr/local/bin/python3.10 scripts/inventory_mcp_registries.py "
        f"--official-pages 20 --glama-pages 50 "
        f">> {LOG_FILE} 2>&1\n"
    )
    sftp = ssh.open_sftp()
    with sftp.file(CRON_FILE, "w") as fh:
        fh.write(cron_body)
    sftp.close()
    _run(ssh, f"chmod 644 {CRON_FILE}")
    print(f"installed {CRON_FILE}")

    code, out = _run(
        ssh,
        f"cd {REMOTE} && set -a && . ./.env 2>/dev/null; set +a && "
        f"/usr/local/bin/python3.10 scripts/inventory_mcp_registries.py "
        f"--official-pages 20 --glama-pages 50",
        timeout=900,
    )
    print(out)
    if code != 0:
        ssh.close()
        print("deploy_mcp_inventory_FAILED run")
        return code

    code2, smoke = _run(
        ssh,
        f"cd {REMOTE} && /usr/local/bin/python3.10 scripts/smoke_mcp_inventory_vps.py --local",
        timeout=120,
    )
    print(smoke)
    ok = code2 == 0 and "smoke_ok" in smoke
    print("deploy_mcp_inventory_ok" if ok else "deploy_mcp_inventory_FAILED smoke")
    ssh.close()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
