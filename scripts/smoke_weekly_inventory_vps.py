#!/usr/bin/env python3
"""Smoke CF-G-6 weekly inventory diff on VPS."""

from __future__ import annotations

import json
import os
import sys

import paramiko

SERVER = "47.112.162.80"
REMOTE = "/opt/lima-router"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))


def main() -> int:
    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)

    _stdin, stdout, _stderr = ssh.exec_command(
        f"cat {REMOTE}/data/inventory_weekly_diff.json 2>/dev/null || echo '{{}}'",
        timeout=30,
    )
    raw = stdout.read().decode("utf-8", errors="replace").strip()
    diff = json.loads(raw) if raw else {}
    print("weekly_diff_keys", sorted(diff.keys()))

    py = (
        "from telegram_digest import build_unified_digest_text; "
        "text = build_unified_digest_text(); "
        "line = next((l for l in text.splitlines() if l.startswith('Inventory 7d:')), ''); "
        "print('digest_inventory_line', line)"
    )
    cmd = f"cd {REMOTE} && set -a && . ./.env && set +a && /usr/local/bin/python3.10 -c {repr(py)}"
    _stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    ssh.close()

    if err:
        print(err, file=sys.stderr)
    print(out)
    ok = "digest_inventory_line Inventory 7d:" in out and "cloudflare" in raw.lower()
    print("smoke_ok" if ok else "smoke_FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
