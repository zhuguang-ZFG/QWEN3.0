#!/usr/bin/env python3
"""Install SearXNG on VPS via Docker/Podman Compose (PE-D-1-2)."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import paramiko

SERVER = "47.112.162.80"
REMOTE = "/opt/lima-searxng"
ROUTER = "/opt/lima-router"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))
ROUTER_FILES = (
    "search_gateway/dev_adapter.py",
    "search_gateway/searxng_adapter.py",
)


def _run(ssh: paramiko.SSHClient, cmd: str, timeout: float = 300) -> tuple[int, str]:
    _stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    channel = stdout.channel
    channel.settimeout(timeout)
    out = (stdout.read() + stderr.read()).decode("utf-8", errors="replace").strip()
    return channel.recv_exit_status(), out


def _run_bg_poll(ssh: paramiko.SSHClient, cmd: str, log: str, timeout: float = 1800) -> tuple[int, str]:
    """Run long command in background; poll log until exit marker or timeout."""
    _run(ssh, f"nohup sh -c {repr(cmd)} > {log} 2>&1; echo DONE >> {log} &")
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(15)
        _code, tail = _run(ssh, f"tail -20 {log} 2>/dev/null || true", timeout=30)
        if "DONE" in tail:
            _code, full = _run(ssh, f"cat {log}", timeout=60)
            ok = "Error:" not in full.split("DONE")[0][-400:]
            return (0 if ok else 1), full[-800:]
    return 1, "timeout waiting for background install"


def main() -> int:
    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    base = Path(__file__).resolve().parents[1]
    for name in ("docker-compose.yml", "settings.yml"):
        local = base / "infra" / "searxng" / name
        if not local.is_file():
            sys.exit(f"missing {local}")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)
    _run(ssh, f"mkdir -p {REMOTE}")
    sftp = ssh.open_sftp()
    sftp.put(str(base / "infra/searxng/docker-compose.yml"), f"{REMOTE}/docker-compose.yml")
    sftp.put(str(base / "infra/searxng/settings.yml"), f"{REMOTE}/settings.yml")
    sftp.close()

    sftp = ssh.open_sftp()
    for rel in ROUTER_FILES:
        local = base / rel
        sftp.put(str(local), f"{ROUTER}/{rel.replace(chr(92), '/')}")
        print(f"uploaded {rel}")
    sftp.close()

    code, out = _run_bg_poll(
        ssh,
        f"cd {REMOTE} && docker compose down 2>/dev/null; "
        "podman pull ghcr.io/searxng/searxng:latest && "
        "docker compose up -d && sleep 5",
        "/tmp/lima-searxng-install.log",
        timeout=1800,
    )
    print(out[-600:])
    listen = _run(ssh, "ss -tlnp 2>/dev/null | grep 8081 || true")[1]
    search = _run(
        ssh,
        "for i in 1 2 3 4 5; do "
        "curl -sf 'http://127.0.0.1:8081/search?q=test&format=json' | head -c 80 && break; "
        "sleep 3; done || true",
        timeout=60,
    )[1]

    _run(
        ssh,
        "grep -q '^SEARXNG_ENABLED=' /opt/lima-router/.env 2>/dev/null && "
        "sed -i 's|^SEARXNG_ENABLED=.*|SEARXNG_ENABLED=1|' /opt/lima-router/.env || "
        "echo 'SEARXNG_ENABLED=1' >> /opt/lima-router/.env; "
        "grep -q '^SEARXNG_BASE_URL=' /opt/lima-router/.env 2>/dev/null && "
        "sed -i 's|^SEARXNG_BASE_URL=.*|SEARXNG_BASE_URL=http://127.0.0.1:8081|' "
        "/opt/lima-router/.env || "
        "echo 'SEARXNG_BASE_URL=http://127.0.0.1:8081' >> /opt/lima-router/.env",
    )
    _run(ssh, "systemctl restart lima-router")
    ssh.close()

    loopback = "127.0.0.1:8081" in listen
    print(f"listen_8081={listen[:120]}")
    print(f"search_head={search}")
    ok = code == 0 and loopback and search.startswith("{")
    print("install_searxng_ok" if ok else "install_searxng_FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
