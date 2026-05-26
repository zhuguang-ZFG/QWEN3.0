#!/usr/bin/env python3
"""Smoke Netdata Agent + MCP endpoint on VPS (PE-C-1)."""

from __future__ import annotations

import json
import os
import sys

import paramiko

SERVER = "47.112.162.80"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))


def _run(ssh: paramiko.SSHClient, cmd: str, timeout: float = 60) -> tuple[int, str]:
    _stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = (stdout.read() + stderr.read()).decode("utf-8", errors="replace").strip()
    code = stdout.channel.recv_exit_status()
    return code, out


def main() -> int:
    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)

    active = _run(ssh, "systemctl is-active netdata 2>/dev/null")[1].strip()
    info_code, info_raw = _run(ssh, "curl -sf http://127.0.0.1:19999/api/v1/info", timeout=30)
    cpu_code, cpu_raw = _run(
        ssh,
        "curl -sf 'http://127.0.0.1:19999/api/v1/data?chart=system.cpu&after=-60&points=1&format=json'",
        timeout=30,
    )
    listen = _run(ssh, "ss -tlnp 2>/dev/null | grep 19999 || true", timeout=15)[1]
    mcp_code, _mcp_body = _run(
        ssh,
        "curl -sf -o /dev/null -w '%{http_code}' http://127.0.0.1:19999/mcp",
        timeout=15,
    )

    version = ""
    if info_code == 0 and info_raw:
        try:
            version = str(json.loads(info_raw).get("version") or "")
        except json.JSONDecodeError:
            version = ""

    version_ok = bool(version) and (
        version.startswith("2.") or version.startswith("v2.")
    )

    ssh.close()

    print(f"netdata_service={active}")
    print(f"netdata_version={version or 'unknown'}")
    print(f"cpu_chart={'ok' if cpu_code == 0 else 'fail'}")
    print(f"mcp_http={mcp_code or '000'}")
    print(f"listen_19999={listen.replace(chr(10), ' ')[:120]}")

    ok = (
        active == "active"
        and info_code == 0
        and cpu_code == 0
        and version_ok
    )
    print("smoke_ok" if ok else "smoke_FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
