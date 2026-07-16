#!/usr/bin/env python3
"""Unified deploy script for LiMa VPS.

Replaces 40+ individual deploy_*.py scripts with one parameterized script.

Usage:
    python deploy_unified.py                    # deploy core files
    python deploy_unified.py --slice all        # deploy everything
    python deploy_unified.py --files a.py b.py  # deploy specific files
    python deploy_unified.py --dry-run          # show what would be deployed
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.deploy_common import format_deploy_ok
from scripts.deploy_unified_helpers import expand_with_dependencies

from scripts.deploy_unified_common import (
    SLICE_FILES,
    HEALTH_WAIT_SECONDS,
    TARGET_ALIYUN,
    TARGET_JDCLOUD,
    _DEPLOY_EXCLUDES,
    _collect_core_files,
    _collect_runtime_files,
    _is_core_path,
    _normalize_deploy_path,
    collect_git_range,
    DeployTarget,
    get_deploy_target,
)
from scripts.deploy_unified_preflight import prepare_remote_deploy, restore_remote_backup
from scripts.deploy_unified_deploy import deploy_files, remove_remote_files
from scripts.deploy_unified_restart import restart_server
from scripts.deploy_unified_nginx import sync_nginx_config


def _collect_files(args, project_root: Path) -> list[str]:
    """Resolve the file list from CLI args."""
    if args.files:
        requested = [_normalize_deploy_path(path) for path in args.files]
        if rejected := [path for path in requested if not _is_core_path(path)]:
            raise ValueError(f"non-runtime deploy path(s): {', '.join(rejected)}")
        exclude_prefixes = tuple(f"{d}/" for d in _DEPLOY_EXCLUDES)
        files = expand_with_dependencies(requested, project_root, exclude_patterns=exclude_prefixes)
        tracked = set(_collect_core_files(project_root))
        if rejected := [path for path in files if path not in tracked]:
            raise ValueError(f"untracked or non-runtime deploy path(s): {', '.join(rejected)}")
        added = [f for f in files if f not in requested]
        if added:
            print(f"  auto-added {len(added)} local dependencies: {', '.join(added)}")
    elif args.slice == "core":
        files = _collect_core_files(project_root)
    elif args.slice == "all":
        files = _collect_runtime_files(project_root)
    else:
        files = SLICE_FILES.get(args.slice, [])
    return list(dict.fromkeys(files))


def _restore_after_failure(backup_path: str, target: DeployTarget, *, restart: bool) -> None:
    if not backup_path:
        return
    print(f"\nDeployment failed; rolling back from {backup_path}...")
    if restore_remote_backup(backup_path, target=target):
        if restart and not restart_server(target=target, prepare=False):
            print("Rollback restart/readiness failed")
    else:
        print("Rollback failed")


def _apply_file_changes(files: list[str], remove_paths: list[str], target: DeployTarget, args, backup_path: str):
    results = (
        deploy_files(files, target=target, dry_run=args.dry_run)
        if files
        else {"uploaded": 0, "failed": [], "skipped": []}
    )
    print(
        f"\nResult: {results['uploaded']} uploaded, {len(results['failed'])} failed, {len(results['skipped'])} skipped"
    )
    if results["failed"] or results["skipped"]:
        for failure in results["failed"]:
            print(f"  FAIL: {failure}")
        for skipped in results["skipped"]:
            print(f"  FAIL: missing local file: {skipped}")
        _restore_after_failure(backup_path, target, restart=False)
        return None
    removed = 0
    if remove_paths:
        removal = remove_remote_files(remove_paths, target=target, dry_run=args.dry_run)
        removed = removal["removed"]
        print(f"Remove: {removed} ok, {len(removal['failed'])} failed")
        if removal["failed"]:
            for failure in removal["failed"]:
                print(f"  FAIL: {failure}")
            _restore_after_failure(backup_path, target, restart=False)
            return None
    return results, removed


def _execute_deploy(files: list[str], remove_paths: list[str], target: DeployTarget, args, backup_path: str) -> int:
    """Run deploy, handle restart, rollback, and notification."""
    changed = _apply_file_changes(files, remove_paths, target, args, backup_path)
    if changed is None:
        return 1
    results, removed = changed

    if args.sync_nginx and not args.dry_run:
        if not sync_nginx_config(target=target, dry_run=args.dry_run):
            _restore_after_failure(backup_path, target, restart=False)
            return 1

    if args.dry_run or args.no_restart:
        return 0

    if results["uploaded"] > 0 or removed > 0:
        print("\nRestarting server...")
        env_update = Path(args.env_update) if args.env_update else None
        ok = restart_server(target=target, env_update=env_update)
        print(f"Health: {'OK' if ok else 'FAILED'} (wait up to {HEALTH_WAIT_SECONDS}s)")

        if not ok:
            _restore_after_failure(backup_path, target, restart=True)
            return 1

        notify_text = format_deploy_ok(
            f"unified/{args.slice}/{target.name}",
            health=f"uploaded={results['uploaded']}",
        )
        print(f"\n{notify_text}")

    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Unified LiMa deploy")
    parser.add_argument(
        "--slice",
        choices=["core", "all"],
        default="core",
        help="Runtime allowlist to deploy; all is a backward-compatible alias for core",
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--files", nargs="+", help="Specific tracked runtime files to deploy")
    source.add_argument(
        "--git-range",
        nargs=2,
        metavar=("BEFORE", "AFTER"),
        help="Deploy core uploads and removals changed between two Git revisions",
    )
    parser.add_argument(
        "--remove",
        nargs="+",
        metavar="PATH",
        help="Relative paths to delete on the remote under the deploy root (after upload)",
    )
    parser.add_argument(
        "--target",
        choices=[TARGET_ALIYUN, TARGET_JDCLOUD],
        default=TARGET_JDCLOUD,
        help="Deploy target VPS (default: jdcloud, the production entry via Cloudflare Tunnel)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deployed")
    parser.add_argument("--no-restart", action="store_true", help="Skip server restart")
    parser.add_argument(
        "--env-update",
        metavar="FILE",
        help="Append keys absent from the remote .env; existing values are never overwritten",
    )
    parser.add_argument(
        "--sync-nginx",
        action="store_true",
        help="Sync deploy/nginx/chat.donglicao.com.conf to the target VPS and reload nginx (default: off)",
    )
    args = parser.parse_args()

    if args.env_update and args.no_restart:
        parser.error("--env-update requires restart/health verification")
    if args.env_update and not Path(args.env_update).is_file():
        parser.error(f"env update file not found: {args.env_update}")
    return args


def _resolve_request(args: argparse.Namespace, project_root: Path) -> tuple[list[str], list[str]]:
    remove_paths = list(dict.fromkeys(_normalize_deploy_path(path) for path in (args.remove or [])))
    if rejected_removals := [path for path in remove_paths if not _is_core_path(path)]:
        raise ValueError(f"non-runtime removal path(s): {', '.join(rejected_removals)}")
    if args.git_range:
        try:
            files, range_removals = collect_git_range(project_root, *args.git_range)
        except (OSError, ValueError, subprocess.CalledProcessError) as exc:
            raise ValueError(f"invalid git range: {exc}") from exc
        remove_paths = list(dict.fromkeys([*remove_paths, *range_removals]))
    elif (
        remove_paths
        and not args.files
        and not any(item == "--slice" or item.startswith("--slice=") for item in sys.argv[1:])
    ):
        files = []
    else:
        files = _collect_files(args, project_root)
    return files, remove_paths


def _prepare_backup(files: list[str], remove_paths: list[str], target: DeployTarget, args: argparse.Namespace) -> str:
    if args.dry_run:
        return ""
    label = "unified-range" if args.git_range else "unified-files" if args.files else f"unified-{args.slice}"
    preflight = prepare_remote_deploy(
        list(dict.fromkeys([*files, *remove_paths])),
        target=target,
        label=label,
    )
    if not preflight["ok"]:
        raise RuntimeError(f"capacity check failed: {preflight['reason']}; capacity: {preflight['capacity']}")
    print(f"Capacity: {preflight['capacity']}")
    print(f"Backup: {preflight['backup_path']}")
    return str(preflight["backup_path"])


def main() -> int:
    args = _parse_args()
    target = get_deploy_target(args.target)
    project_root = Path(__file__).resolve().parent.parent
    try:
        files, remove_paths = _resolve_request(args, project_root)
    except ValueError as exc:
        print(f"invalid deploy request: {exc}")
        return 1
    if not files and not remove_paths:
        print("no runtime changes in git range" if args.git_range else "nothing to deploy or remove")
        return 0 if args.git_range else 1
    if files:
        print(f"Deploying {len(files)} files ({args.slice}) to {target.name} ({target.host})...")
    if remove_paths:
        print(f"Will remove {len(remove_paths)} remote path(s) on {target.name}")
    try:
        backup_path = _prepare_backup(files, remove_paths, target, args)
    except RuntimeError as exc:
        print(f"preflight failed: {exc}")
        return 1
    return _execute_deploy(files, remove_paths, target, args, backup_path)


if __name__ == "__main__":
    sys.exit(main())
