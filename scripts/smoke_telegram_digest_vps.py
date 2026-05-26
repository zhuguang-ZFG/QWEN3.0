#!/usr/bin/env python3
"""VPS smoke: build + optionally send unified Telegram digest (TG-GH-3)."""

from __future__ import annotations

import argparse
import os
import sys

import paramiko

SERVER = "47.112.162.80"
REMOTE = "/opt/lima-router"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--send", action="store_true", help="Send digest to Telegram")
    args = parser.parse_args()

    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    fn = "send_unified_digest" if args.send else "build_unified_digest_text"
    py = (
        f"import asyncio; from telegram_digest import {fn}; "
        f"r=asyncio.run({fn}()) if '{fn}'.startswith('send') else {fn}(); "
        f"print('OK', r if isinstance(r, bool) else (r[:200] if r else ''))"
    )
    cmd = f"cd {REMOTE} && set -a && . ./.env && set +a && /usr/local/bin/python3.10 -c {repr(py)}"

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)
    _stdin, stdout, stderr = ssh.exec_command(cmd, timeout=90)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    ssh.close()

    if err:
        print(err, file=sys.stderr)
    print(out)
    return 0 if out.startswith("OK") else 1


if __name__ == "__main__":
    raise SystemExit(main())
