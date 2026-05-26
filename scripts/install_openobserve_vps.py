#!/usr/bin/env python3
"""Install OpenObserve on LiMa VPS via Docker Compose (PE-C-2)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import paramiko

SERVER = "47.112.162.80"
REMOTE = "/opt/lima-openobserve"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))


def _run(ssh: paramiko.SSHClient, cmd: str, timeout: float = 300) -> tuple[int, str]:
    _stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = (stdout.read() + stderr.read()).decode("utf-8", errors="replace").strip()
    code = stdout.channel.recv_exit_status()
    return code, out


def main() -> int:
    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    base = Path(__file__).resolve().parents[1]
    compose = base / "infra" / "openobserve" / "docker-compose.yml"
    if not compose.is_file():
        sys.exit(f"missing {compose}")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)

    _run(ssh, f"mkdir -p {REMOTE}")
    sftp = ssh.open_sftp()
    sftp.put(str(compose), f"{REMOTE}/docker-compose.yml")
    sftp.close()

    pw = os.environ.get("OPENOBSERVE_PASSWORD", "change-me-local")
    user = os.environ.get("OPENOBSERVE_USER", "root@example.com")

    sftp = ssh.open_sftp()
    with sftp.file(f"{REMOTE}/.env", "w") as remote_env:
        remote_env.write(f"OPENOBSERVE_USER={user}\nOPENOBSERVE_PASSWORD={pw}\n")
    sftp.close()

    code, out = _run(
        ssh,
        f"cd {REMOTE} && docker compose down 2>/dev/null; "
        "docker compose pull && docker compose up -d --force-recreate",
        timeout=600,
    )
    print(out[-800:])
    listen = _run(ssh, "ss -tlnp 2>/dev/null | grep 5080 || true")[1]
    health = _run(
        ssh,
        f"curl -sf -o /dev/null -w '%{{http_code}}' http://127.0.0.1:5080 || true",
    )[1]

    # append lima-router .env hints (no password in echo)
    env_lines = (
        "grep -q '^OPENOBSERVE_ENABLED=' /opt/lima-router/.env 2>/dev/null || "
        "echo 'OPENOBSERVE_ENABLED=0' >> /opt/lima-router/.env; "
        "grep -q '^OPENOBSERVE_URL=' /opt/lima-router/.env 2>/dev/null || "
        "echo 'OPENOBSERVE_URL=http://127.0.0.1:5080' >> /opt/lima-router/.env; "
        "grep -q '^OPENOBSERVE_ORG=' /opt/lima-router/.env 2>/dev/null || "
        f"echo 'OPENOBSERVE_ORG=default' >> /opt/lima-router/.env; "
        f"grep -q '^OPENOBSERVE_PASSWORD=' /opt/lima-router/.env 2>/dev/null || "
        f"echo 'OPENOBSERVE_PASSWORD={pw}' >> /opt/lima-router/.env"
    )
    _run(ssh, env_lines)

    ssh.close()
    loopback = "127.0.0.1:5080" in listen
    print(f"listen_5080={listen[:120]}")
    print(f"http_code={health}")
    ok = code == 0 and loopback
    print("install_openobserve_ok" if ok else "install_openobserve_FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
