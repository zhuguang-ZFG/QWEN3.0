#!/usr/bin/env python3
"""VPS diagnostic: GITEE_TOKEN configured (no secret output)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from deploy_common import KEY, REMOTE, SERVER


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)
    cmds = [
        f"grep -c '^GITEE_TOKEN=' {REMOTE}/.env 2>/dev/null || echo 0",
        f"grep '^GITEE' {REMOTE}/.env 2>/dev/null | cut -d= -f1 || true",
        f"test -f {REMOTE}/.env && wc -c {REMOTE}/.env || echo noenv",
        f"cd {REMOTE} && /usr/local/bin/python3.10 scripts/smoke_gitee_mcp_tools.py",
    ]
    for cmd in cmds:
        _i, o, e = ssh.exec_command(cmd, timeout=90)
        print((o.read() + e.read()).decode("utf-8", errors="replace").strip())
    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
