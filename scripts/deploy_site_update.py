#!/usr/bin/env python3
"""Deploy updated donglicao-site (official site + chat UI) to VPS.

Usage:
    python scripts/deploy_site_update.py              # deploy both
    python scripts/deploy_site_update.py --dry-run    # show plan only
    python scripts/deploy_site_update.py --site-only  # official site only
    python scripts/deploy_site_update.py --chat-only  # chat UI only
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.deploy_common import SERVER, KEY, configure_ssh_host_keys

import paramiko

# Paths
SITE_DIR = Path(__file__).resolve().parent.parent / "donglicao-site"
INDEX_HTML = SITE_DIR / "index.html"
CHAT_HTML = SITE_DIR / "chat.html"

# VPS targets
VPS_SITE_DIR = "/www/wwwroot/donglicao-site"
VPS_CHAT_DIR = "/var/www/chat"
VPS_BACKUP_DIR = "/root/site-backups"


def backup_remote(ssh: paramiko.SSHClient, label: str) -> str:
    """Create a timestamped backup of current site files on VPS."""
    ts = time.strftime("%Y%m%d_%H%M%S")
    backup_path = f"{VPS_BACKUP_DIR}/{label}-{ts}"
    cmds = [
        f"mkdir -p {backup_path}",
        f"cp -a {VPS_SITE_DIR}/index.html {backup_path}/donglicao-index.html 2>/dev/null || true",
        f"cp -a {VPS_CHAT_DIR}/index.html {backup_path}/chat-index.html 2>/dev/null || true",
    ]
    for cmd in cmds:
        stdin, stdout, stderr = ssh.exec_command(cmd)
        stdout.read()
    print(f"  Backup: {backup_path}")
    return backup_path


def upload_file(sftp: paramiko.SFTPClient, local: Path, remote: str) -> bool:
    """Upload a single file via SFTP."""
    if not local.exists():
        print(f"  MISSING: {local}")
        return False
    size = local.stat().st_size
    sftp.put(str(local), remote)
    remote_stat = sftp.stat(remote)
    ok = remote_stat.st_size == size
    status = "OK" if ok else "SIZE_MISMATCH"
    print(f"  Upload {status}: {local.name} -> {remote} ({size}B)")
    return ok


def smoke_check(url: str, label: str) -> bool:
    """Quick HTTP check that the URL returns 200."""
    import urllib.request
    try:
        req = urllib.request.Request(url, method="GET")
        req.add_header("User-Agent", "LiMa-Deploy/1.0")
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read(2048).decode("utf-8", errors="replace")
            code = resp.status
            # Check for key markers
            has_lima = "LiMa" in body or "lima" in body.lower()
            ok = code == 200 and has_lima
            print(f"  Smoke {label}: HTTP {code}, has_lima={has_lima}, ok={ok}")
            return ok
    except Exception as e:
        print(f"  Smoke {label}: ERROR {e}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy donglicao-site update to VPS")
    parser.add_argument("--dry-run", action="store_true", help="Show plan without deploying")
    parser.add_argument("--site-only", action="store_true", help="Only deploy official site")
    parser.add_argument("--chat-only", action="store_true", help="Only deploy chat UI")
    args = parser.parse_args()

    deploy_site = not args.chat_only
    deploy_chat = not args.site_only

    print(f"=== LiMa Site Deploy ===")
    print(f"Target: {SERVER}")
    print(f"Official site: {deploy_site}")
    print(f"Chat UI: {deploy_chat}")

    if not INDEX_HTML.exists():
        print(f"ERROR: {INDEX_HTML} not found")
        return 1
    if deploy_chat and not CHAT_HTML.exists():
        print(f"ERROR: {CHAT_HTML} not found")
        return 1

    print(f"\nFiles to deploy:")
    if deploy_site:
        print(f"  {INDEX_HTML.name} ({INDEX_HTML.stat().st_size}B) -> {VPS_SITE_DIR}/index.html")
    if deploy_chat:
        print(f"  {CHAT_HTML.name} ({CHAT_HTML.stat().st_size}B) -> {VPS_CHAT_DIR}/index.html")

    if args.dry_run:
        print("\n[DRY RUN] No changes made.")
        return 0

    # Connect
    print(f"\nConnecting to {SERVER}...")
    ssh = paramiko.SSHClient()
    configure_ssh_host_keys(ssh)

    key_path = KEY
    if not os.path.exists(key_path):
        print(f"ERROR: SSH key not found: {key_path}")
        return 1

    ssh.connect(SERVER, username="root", key_filename=key_path, timeout=15)
    print("Connected.")

    try:
        # Backup
        print("\n--- Backup ---")
        backup_path = backup_remote(ssh, "site-update")

        sftp = ssh.open_sftp()

        # Deploy official site
        if deploy_site:
            print("\n--- Official Site (donglicao.com) ---")
            ok = upload_file(sftp, INDEX_HTML, f"{VPS_SITE_DIR}/index.html")
            if not ok:
                print("ERROR: Official site upload failed")
                return 1

        # Deploy chat UI
        if deploy_chat:
            print("\n--- Chat UI (chat.donglicao.com) ---")
            # Ensure target directory exists
            ssh.exec_command(f"mkdir -p {VPS_CHAT_DIR}")
            time.sleep(0.5)
            ok = upload_file(sftp, CHAT_HTML, f"{VPS_CHAT_DIR}/index.html")
            if not ok:
                print("ERROR: Chat UI upload failed")
                return 1

        sftp.close()

        # Smoke tests
        print("\n--- Smoke Tests ---")
        results = []
        if deploy_site:
            results.append(smoke_check("https://donglicao.com", "official-site"))
            results.append(smoke_check("https://www.donglicao.com", "www-site"))
        if deploy_chat:
            results.append(smoke_check("https://chat.donglicao.com", "chat-ui"))

        # Health check (always)
        results.append(smoke_check("https://chat.donglicao.com/health", "chat-health"))

        all_ok = all(results)
        print(f"\n{'='*40}")
        if all_ok:
            print("DEPLOY OK: All smoke tests passed")
            print(f"Backup: {backup_path}")
        else:
            print("DEPLOY WARNING: Some smoke tests failed")
            print(f"Backup: {backup_path}")
            print("Review the issues above. Rollback command:")
            print(f"  cp {backup_path}/donglicao-index.html {VPS_SITE_DIR}/index.html")
            print(f"  cp {backup_path}/chat-index.html {VPS_CHAT_DIR}/index.html")

        return 0 if all_ok else 2

    finally:
        ssh.close()


if __name__ == "__main__":
    sys.exit(main())
