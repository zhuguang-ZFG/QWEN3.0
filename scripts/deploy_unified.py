#!/usr/bin/env python3
"""Unified deploy script for LiMa VPS.

Replaces 40+ individual deploy_*.py scripts with one parameterized script.

Usage:
    python deploy_unified.py                    # deploy core files
    python deploy_unified.py --slice phase_a    # deploy Phase A
    python deploy_unified.py --slice phase_b    # deploy Phase B
    python deploy_unified.py --slice all        # deploy everything
    python deploy_unified.py --files a.py b.py  # deploy specific files
    python deploy_unified.py --dry-run          # show what would be deployed
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.deploy_common import (
    SERVER,
    REMOTE,
    KEY,
    configure_ssh_host_keys,
    format_deploy_ok,
)
from scripts.deploy_unified_helpers import expand_with_dependencies

import paramiko

from scripts.deploy_unified_common import (
    CORE_FILES,
    CORE_DIRS,
    SLICE_FILES,
    HEALTH_WAIT_SECONDS,
    _DEPLOY_EXCLUDES,
    _collect_runtime_files,
    parse_capacity_output,
    capacity_result,
)
from scripts.deploy_unified_preflight import prepare_remote_deploy, restore_remote_backup
from scripts.deploy_unified_deploy import deploy_files
from scripts.deploy_unified_restart import restart_server
from scripts.deploy_unified_nginx import sync_nginx_config


def _collect_files(args, project_root: Path) -> list[str]:
    """Resolve the file list from CLI args."""
    if args.files:
        exclude_prefixes = tuple(f"{d}/" for d in _DEPLOY_EXCLUDES)
        files = expand_with_dependencies(args.files, project_root, exclude_patterns=exclude_prefixes)
        added = [f for f in files if f not in args.files]
        if added:
            print(f"  auto-added {len(added)} local dependencies: {', '.join(added)}")
    elif args.slice in ("core", "all"):
        files = _collect_runtime_files(project_root)
    else:
        files = SLICE_FILES.get(args.slice, [])
    return list(dict.fromkeys(files))


def _execute_deploy(files: list[str], args, backup_path: str) -> int:
    """Run deploy, handle restart, rollback, and notification."""
    results = deploy_files(files, dry_run=args.dry_run)

    print(
        f"\nResult: {results['uploaded']} uploaded, {len(results['failed'])} failed, {len(results['skipped'])} skipped"
    )
    if results["failed"]:
        for f in results["failed"]:
            print(f"  FAIL: {f}")
        return 1

    if args.sync_nginx and not args.dry_run:
        if not sync_nginx_config(dry_run=args.dry_run):
            return 1

    if args.dry_run or args.no_restart:
        return 0

    if results["uploaded"] > 0:
        print("\nRestarting server...")
        ok = restart_server()
        print(f"Health: {'OK' if ok else 'FAILED'} (wait up to {HEALTH_WAIT_SECONDS}s)")

        if not ok:
            if backup_path:
                print(f"\nHealth check failed; rolling back from {backup_path}...")
                if restore_remote_backup(backup_path):
                    restart_server()
                else:
                    print("Rollback failed")
            return 1

        notify_text = format_deploy_ok(
            f"unified/{args.slice}",
            health=f"uploaded={results['uploaded']}",
        )
        print(f"\n{notify_text}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Unified LiMa deploy")
    parser.add_argument(
        "--slice",
        choices=["core", "phase_a", "phase_b", "all"],
        default="core",
        help="Which slice to deploy",
    )
    parser.add_argument("--files", nargs="+", help="Specific files to deploy")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deployed")
    parser.add_argument("--no-restart", action="store_true", help="Skip server restart")
    parser.add_argument(
        "--sync-nginx",
        action="store_true",
        help="Sync _nginx_chat_temp.conf to VPS and reload nginx (default: off)",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    files = _collect_files(args, project_root)
    print(f"Deploying {len(files)} files ({args.slice})...")

    backup_path = ""
    if not args.dry_run:
        backup_label = "unified-files" if args.files else f"unified-{args.slice}"
        try:
            preflight = prepare_remote_deploy(files, label=backup_label)
        except RuntimeError as exc:
            print(f"preflight failed: {exc}")
            return 1
        if not preflight["ok"]:
            print(f"capacity check failed: {preflight['reason']}")
            print(f"capacity: {preflight['capacity']}")
            return 1
        print(f"Capacity: {preflight['capacity']}")
        print(f"Backup: {preflight['backup_path']}")
        backup_path = str(preflight["backup_path"])

    return _execute_deploy(files, args, backup_path)


if __name__ == "__main__":
    sys.exit(main())
