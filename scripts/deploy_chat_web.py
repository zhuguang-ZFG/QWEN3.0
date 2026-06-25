#!/usr/bin/env python3
"""Deploy the LiMa Chat Web static files to the VPS via paramiko.

Source: chat-web/
Target (VPS): /var/www/chat/

The script backs up the remote files before overwriting them and reloads nginx
so the new files are served immediately.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import paramiko

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import deploy_config

from scripts.deploy_common import (
    KEY,
    configure_ssh_host_keys,
)

CHAT_WEB_DIR = PROJECT_ROOT / "chat-web"
REMOTE_HOST = deploy_config.deploy_host()
REMOTE_DIR = "/var/www/chat"
FILES = [
    "index.html",
    "voice-call.html",
    "login.html",
    "register.html",
    "keys.html",
    "usage.html",
    "devices.html",
    "playground.html",
    "styles.css",
    "icons.svg",
    "chat-ui.js",
    "chat-messages.js",
    "chat-api.js",
    "solar-system.js",
    "js/api.js",
    "js/auth.js",
    "js/keys.js",
    "js/usage.js",
    "js/devices.js",
    "js/playground-ui.js",
    "js/playground-utils.js",
    "js/playground.js",
]


def _connect() -> paramiko.SSHClient:
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    configure_ssh_host_keys(ssh)
    user, host = REMOTE_HOST.split("@", 1) if "@" in REMOTE_HOST else ("root", REMOTE_HOST)
    password = deploy_config.deploy_pass()
    try:
        ssh.connect(host, username=user, key_filename=KEY, timeout=15)
    except paramiko.SSHException:
        if not password:
            raise
        ssh.connect(host, username=user, password=password, timeout=15)
    return ssh


def _exec(ssh: paramiko.SSHClient, command: str) -> tuple[int, str, str]:
    print(f"$ {command}")
    _stdin, stdout, stderr = ssh.exec_command(command)
    code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    if out:
        print(out)
    if err:
        print(err, file=sys.stderr)
    return code, out, err


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

    ssh = _connect()
    try:
        sftp = ssh.open_sftp()
        try:
            for remote_name in FILES:
                local = CHAT_WEB_DIR / remote_name
                remote_path = f"{REMOTE_DIR}/{remote_name}"
                backup_cmd = f"cp {remote_path} {remote_path}.bak.$(date +%Y%m%d%H%M%S) 2>/dev/null || true"
                _exec(ssh, backup_cmd)
                print(f"uploading {remote_name}...")
                sftp.put(str(local), remote_path)
        finally:
            sftp.close()

        code, _out, _err = _exec(ssh, "nginx -t && systemctl reload nginx")
        if code != 0:
            print("nginx reload failed", file=sys.stderr)
            return code
    finally:
        ssh.close()

    print("Chat Web deployed successfully.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy LiMa Chat Web to VPS")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be copied")
    args = parser.parse_args()
    return deploy(dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
