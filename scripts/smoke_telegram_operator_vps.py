#!/usr/bin/env python3
"""VPS smoke for TG-GH-4 operator tools (/github + /device)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import paramiko

SERVER = "47.112.162.80"
REMOTE = "/opt/lima-router"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))


def main() -> int:
    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    py = (
        "import asyncio; "
        "from telegram_operator_tools import fetch_github_file_text, fetch_device_gateway_status; "
        "gh = fetch_github_file_text('psf/requests', 'README.md', 'main', max_chars=120); "
        "ok_gh = gh.startswith('[') and len(gh) > 20; "
        "dg = asyncio.run(fetch_device_gateway_status(root='http://127.0.0.1:8080')); "
        "ok_dg = 'Device Gateway' in dg and 'ok' in dg.lower(); "
        "print('github_ok', ok_gh, gh[:80].replace(chr(10), ' ')); "
        "print('device_ok', ok_dg, dg.replace(chr(10), ' | ')); "
        "print('smoke_ok' if ok_gh and ok_dg else 'smoke_FAILED')"
    )
    cmd = f"cd {REMOTE} && set -a && . ./.env && set +a && /usr/local/bin/python3.10 -c {repr(py)}"

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)
    _stdin, stdout, stderr = ssh.exec_command(cmd, timeout=90)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()

    if err:
        print(err, file=sys.stderr)
    print(out)
    ok = "smoke_ok" in out
    if ok:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import deploy_common

        deploy_common.notify_smoke_success(ssh, "telegram_operator", detail=out.replace("\n", " | ")[:200])
    ssh.close()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
