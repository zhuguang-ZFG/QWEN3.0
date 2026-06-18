#!/usr/bin/env python3
"""Deploy the LiMa Chat Web static files to the VPS.

Source: chat-web/
Target (VPS): /var/www/chat/

The script backs up the remote files before overwriting them and reloads nginx
so the new files are served immediately.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHAT_WEB_DIR = PROJECT_ROOT / "chat-web"
REMOTE_HOST = os.environ.get("LIMA_DEPLOY_HOST", "root@47.112.162.80")
REMOTE_DIR = "/var/www/chat"
FILES = [
    "index.html",
    "voice-call.html",
    "styles.css",
    "icons.svg",
    "chat-ui.js",
    "chat-messages.js",
    "chat-api.js",
    "solar-system.js",
]


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    print("$", " ".join(cmd))
    return subprocess.run(cmd, check=check)


def deploy(dry_run: bool = False) -> int:
    if not CHAT_WEB_DIR.exists():
        print(f"Error: source directory not found: {CHAT_WEB_DIR}", file=sys.stderr)
        return 1

    missing = [f for f in FILES if not (CHAT_WEB_DIR / f).exists()]
    if missing:
        print(f"Error: missing source files: {missing}", file=sys.stderr)
        return 1

    if dry_run:
        print("Dry run - would copy:")
        for f in FILES:
            print(f"  {CHAT_WEB_DIR / f} -> {REMOTE_HOST}:{REMOTE_DIR}/{f}")
        return 0

    for f in FILES:
        src = CHAT_WEB_DIR / f
        backup_cmd = [
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            REMOTE_HOST,
            f"cp {REMOTE_DIR}/{f} {REMOTE_DIR}/{f}.bak.$(date +%Y%m%d%H%M%S) 2>/dev/null || true",
        ]
        run(backup_cmd)
        run(["scp", str(src), f"{REMOTE_HOST}:{REMOTE_DIR}/{f}"])

    reload_cmd = [
        "ssh",
        "-o",
        "StrictHostKeyChecking=no",
        REMOTE_HOST,
        "nginx -t && systemctl reload nginx",
    ]
    run(reload_cmd)

    print("Chat Web deployed successfully.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy LiMa Chat Web to VPS")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be copied")
    args = parser.parse_args()
    return deploy(dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
