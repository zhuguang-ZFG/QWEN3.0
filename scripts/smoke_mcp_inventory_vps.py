#!/usr/bin/env python3
"""Smoke MCP snapshot — local (--local) or via SSH from dev machine."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REMOTE = "/opt/lima-router"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))
SERVER = "47.112.162.80"


def _check_snapshot(raw: str) -> int:
    if not raw.strip():
        print("smoke_FAILED missing snapshot")
        return 1
    data = json.loads(raw)
    counts = data.get("counts") or {}
    merged = int(counts.get("merged") or 0)
    glama = int(counts.get("glama") or 0)
    official = int(counts.get("official") or 0)
    print(
        f"mcp_snapshot merged={merged} official={official} glama={glama} "
        f"generated_at={data.get('generated_at', '')}"
    )
    ok = merged >= 100 and glama >= 50
    print("smoke_ok" if ok else "smoke_FAILED")
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--local",
        action="store_true",
        help="Read data/mcp_registry_snapshot.json on this host (VPS cron path)",
    )
    parser.add_argument(
        "--root",
        default=os.environ.get("LIMA_ROUTER_ROOT", REMOTE),
        help="LiMa router root when --local",
    )
    args = parser.parse_args()

    if args.local:
        path = Path(args.root) / "data" / "mcp_registry_snapshot.json"
        return _check_snapshot(path.read_text(encoding="utf-8"))

    import paramiko

    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)
    _stdin, stdout, _stderr = ssh.exec_command(
        f"cat {REMOTE}/data/mcp_registry_snapshot.json",
        timeout=60,
    )
    raw = stdout.read().decode("utf-8", errors="replace")
    ssh.close()
    return _check_snapshot(raw)


if __name__ == "__main__":
    raise SystemExit(main())
