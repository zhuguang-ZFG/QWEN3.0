#!/usr/bin/env python3
"""Deploy review slice P2-26: Pyright enforce + Litestream + Filesystem MCP."""

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
    # Pyright fixes (type annotations + real bug fixes)
    "agent_runtime/cli.py",
    "agent_runtime/orchestrator_io.py",
    "channel_gateway/integrations.py",
    "channel_gateway/public_apis_lookup.py",
    "context_pipeline/cache.py",
    "context_pipeline/ensemble.py",
    "context_pipeline/event_log.py",
    "routes/chat_fallback.py",
    "routes/chat_handler.py",
    "routes/chat_preflight.py",
    "routes/ops_metrics.py",
    "routes/quality_gate.py",
    "routes/v3_adapters.py",
    "routing_engine.py",
    "smart_router.py",
    # Filesystem MCP
    "lima_mcp/__init__.py",
    "lima_mcp/tools.py",
    "lima_mcp/fs_allowlist.py",
    # VPS sync: quality_gate sub-modules (must accompany quality_gate.py)
    "routes/quality_gate_direct.py",
    "routes/quality_gate_tiers.py",
    # Litestream config
    "litestream.yml",
]

# systemd unit needs explicit handling (different target dir)
SYSTEMD_UNIT = "infra/vps/systemd/lima-router.service"
SYSTEMD_TARGET = "/etc/systemd/system/lima-router.service"


def main() -> int:
    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    base = Path(__file__).resolve().parent.parent
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)

    # Create all needed remote dirs first (via exec_command before sftp)
    dirs = set()
    for rel in FILES + [SYSTEMD_UNIT]:
        remote = f"{REMOTE}/{rel.replace(chr(92), '/')}"
        dirs.add(os.path.dirname(remote))
    ssh.exec_command(f"mkdir -p {' '.join(dirs)}")
    time.sleep(1)

    # Upload runtime files
    sftp = ssh.open_sftp()
    for rel in FILES:
        local = base / rel
        if not local.is_file():
            sys.exit(f"missing local file: {rel}")
        remote = f"{REMOTE}/{rel.replace(chr(92), '/')}"
        sftp.put(str(local), remote)
        print(f"uploaded {rel}")

    # Upload systemd unit
    local_unit = base / SYSTEMD_UNIT
    if local_unit.is_file():
        sftp.put(str(local_unit), SYSTEMD_TARGET)
        print("updated systemd unit")

    sftp.close()
    time.sleep(1)

    ssh.exec_command("systemctl daemon-reload")
    print("daemon-reload done")

    # Remote compile check
    _i, o, _e = ssh.exec_command(
        f"cd {REMOTE} && /usr/local/bin/python3.10 -m py_compile routing_engine.py"
    )
    compile_err = o.read().decode() + _e.read().decode()
    if compile_err.strip():
        print("COMPILE ERROR:", compile_err[:500])
        ssh.close()
        return 1
    print("remote compile OK")

    # Restart
    ssh.exec_command("systemctl restart lima-router")
    time.sleep(8)
    _i, o, _e = ssh.exec_command("systemctl is-active lima-router")
    status = o.read().decode().strip()
    print("service:", status)
    if status != "active":
        ssh.close()
        return 1

    # Health check
    _i, o, _e = ssh.exec_command(
        "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/health"
    )
    health_code = o.read().decode().strip()
    print("VPS /health:", health_code)
    if health_code != "200":
        ssh.close()
        return 1

    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
