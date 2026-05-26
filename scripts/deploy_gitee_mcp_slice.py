#!/usr/bin/env python3
"""Deploy Gitee search MCP tools slice."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import paramiko

from deploy_common import KEY, REMOTE, SERVER, notify_deploy_success, notify_smoke_success

FILES = [
    "gitee_mirror.py",
    "search_gateway/gitee_tools.py",
    "search_gateway/dev_tools.py",
    "search_gateway/safety.py",
    "lima_mcp/__init__.py",
    "lima_mcp/tools.py",
    "tool_gateway/registry.py",
    "scripts/smoke_gitee_mcp_tools.py",
    "scripts/provision_gitee_token_vps.py",
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
    _run(ssh, f"mkdir -p {REMOTE}/search_gateway {REMOTE}/lima_mcp {REMOTE}/tool_gateway {REMOTE}/scripts")
    for rel in FILES:
        local = base / rel
        remote = f"{REMOTE}/{rel.replace(chr(92), '/')}"
        sftp.put(str(local), remote)
        print(f"uploaded {rel}")
    sftp.close()

    _run(ssh, "systemctl restart lima-router", timeout=60)
    time.sleep(3)

    smoke_cmd = f"cd {REMOTE} && /usr/local/bin/python3.10 scripts/smoke_gitee_mcp_tools.py"
    code, smoke_out = _run(ssh, smoke_cmd, timeout=60)
    print(smoke_out)

    _, health = _run(ssh, "curl -sf http://127.0.0.1:8080/health", timeout=30)
    ok = code == 0 and "smoke_gitee_mcp_ok" in smoke_out and bool(health)
    notify_deploy_success(ssh, "gitee-mcp", service="lima-router", health=health[:160])
    if ok:
        notify_smoke_success(ssh, "Gitee MCP tools", detail=smoke_out[:200])
    ssh.close()
    print("deploy_gitee_mcp_ok" if ok else "deploy_gitee_mcp_fail")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
