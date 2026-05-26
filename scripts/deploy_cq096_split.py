#!/usr/bin/env python3
"""Deploy CQ-096 device_gateway + router_http split to LiMa VPS."""

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
    "router_http.py",
    "router_http_body.py",
    "router_http_scnet.py",
    "router_http_vision.py",
    "routes/device_gateway.py",
    "routes/device_gateway_dispatch.py",
    "routes/device_gateway_ws.py",
]


def _run(ssh: paramiko.SSHClient, cmd: str, timeout: float | None = None) -> str:
    _stdin, stdout, stderr = ssh.exec_command(cmd)
    if timeout is not None:
        stdout.channel.settimeout(timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        out = (out + "\n" + err).strip()
    return out


def _log(msg: str) -> None:
    print(msg, flush=True)


def _restart_router(ssh: paramiko.SSHClient) -> None:
    _run(ssh, "systemctl stop lima-router 2>/dev/null || true")
    _run(ssh, "pkill -9 -f 'uvicorn server:app' || true")
    _run(ssh, "pkill -9 -f 'python3.10 server.py' || true")
    _run(ssh, "fuser -k 8080/tcp 2>/dev/null || true")
    time.sleep(3)
    _run(ssh, "systemctl reset-failed lima-router 2>/dev/null || true")
    out = _run(ssh, "systemctl start lima-router 2>&1", timeout=15)
    if out:
        _log(out[:200])
    time.sleep(8)


def main() -> int:
    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    base = Path(__file__).resolve().parent.parent
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, banner_timeout=30, timeout=60)

    _log("deploy CQ-096 split (no VPS backup; rollback via GitHub)")

    sftp = ssh.open_sftp()
    for rel in FILES:
        local = base / rel
        if not local.is_file():
            sftp.close()
            ssh.close()
            sys.exit(f"missing local file: {local}")
        remote = f"{REMOTE}/{rel}"
        sftp.put(str(local), remote)
        _log(f"uploaded {rel} ({local.stat().st_size} bytes)")
    sftp.close()

    _restart_router(ssh)

    active = _run(ssh, "systemctl is-active lima-router 2>/dev/null").strip()
    port = _run(ssh, "ss -tlnp | grep 8080 || true")
    health = _run(ssh, "curl -sf http://127.0.0.1:8080/health | head -c 160")
    device = _run(ssh, "curl -sf http://127.0.0.1:8080/device/v1/health | head -c 240")

    _log(f"service={active}")
    _log(f"port={port[:120]}")
    _log(f"health={health}")
    _log(f"device_health={device}")

    ok = active == "active" and "8080" in port and '"status"' in health
    if not ok:
        _log(_run(ssh, "journalctl -u lima-router -n 12 --no-pager"))
        ssh.close()
        return 1

    ssh.close()
    _log("deploy_cq096_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
