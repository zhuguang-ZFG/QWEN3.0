#!/usr/bin/env python3
"""Unified deploy script for LiMa VPS.

Replaces 40+ individual deploy_*.py scripts with one parameterized script.

Usage:
    python deploy_unified.py                    # deploy core files
    python deploy_unified.py --slice m1m5       # deploy M1-M5 modules
    python deploy_unified.py --slice phase_a    # deploy Phase A
    python deploy_unified.py --slice all        # deploy everything
    python deploy_unified.py --files a.py b.py  # deploy specific files
    python deploy_unified.py --dry-run          # show what would be deployed
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.deploy_common import (
    SERVER,
    REMOTE,
    KEY,
    configure_ssh_host_keys,
    format_deploy_ok,
)

import paramiko


CORE_FILES = [
    "server.py",
    "routing_engine.py",
    "routing_selector.py",
    "router_v3.py",
    "router_classifier.py",
    "smart_router.py",
    "health_tracker.py",
    "sticky_session.py",
    "rate_limiter.py",
    "budget_manager.py",
    "capability_matrix.py",
    "route_post_process.py",
]

CORE_DIRS = [
    "routes",
    "context_pipeline",
    "session_memory",
    "agent_runtime",
    "code_context",
    "search_gateway",
    "channel_gateway",
    "observability",
]

SLICE_FILES = {
    "m1m5": [
        "agent_runtime/shell_executor.py",
        "agent_runtime/git_executor.py",
        "agent_runtime/network_executor.py",
        "agent_runtime/real_executor.py",
        "code_context/treesitter_adapter.py",
        "code_context/sqlite_graph_store.py",
        "code_context/chroma_vector_store.py",
        "code_context/file_watcher.py",
        "code_context/ast_adapter.py",
        "code_context/graph_index.py",
        "code_context/scanner.py",
        "code_context/index_store.py",
        "context_pipeline/memory_persistence.py",
        "context_pipeline/routing_bridge.py",
        "context_pipeline/hierarchical_memory.py",
        "developer_skills/__init__.py",
        "developer_skills/investigate.py",
        "developer_skills/review.py",
        "developer_skills/ship.py",
        "developer_skills/learn.py",
        "research/__init__.py",
        "research/orchestrator.py",
        "research/source_adapters.py",
        "research/synthesizer.py",
    ],
    "phase_a": [
        "context_pipeline/code_context_injection.py",
        "routing_engine.py",
        "routing_selector.py",
    ],
    "phase_b": [
        "context_pipeline/response_validator.py",
        "context_pipeline/auto_indexer.py",
        "context_pipeline/session_memory_enhancer.py",
        "route_post_process.py",
    ],
}

HEALTH_WAIT_SECONDS = 90
HEALTH_POLL_SECONDS = 2


def ensure_remote_dir(sftp: paramiko.SFTPClient, remote_dir: str) -> None:
    """Create a remote directory tree using SFTP only."""
    normalized = remote_dir.replace("\\", "/")
    parts = [part for part in normalized.split("/") if part]
    current = "/" if normalized.startswith("/") else ""

    for part in parts:
        current = f"{current.rstrip('/')}/{part}" if current else part
        try:
            sftp.stat(current)
        except (FileNotFoundError, OSError):
            try:
                sftp.mkdir(current)
            except OSError:
                sftp.stat(current)


def deploy_files(files: list[str], *, dry_run: bool = False) -> dict:
    """Deploy a list of files to VPS via SFTP."""
    project_root = Path(__file__).resolve().parent.parent
    results = {"uploaded": 0, "failed": [], "skipped": []}

    if dry_run:
        for f in files:
            local = project_root / f
            if local.exists():
                print(f"  WOULD UPLOAD: {f}")
                results["uploaded"] += 1
            else:
                print(f"  SKIP (not found): {f}")
                results["skipped"].append(f)
        return results

    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    configure_ssh_host_keys(ssh)
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=15)

    sftp = ssh.open_sftp()
    try:
        for f in files:
            local = project_root / f
            if not local.exists():
                results["skipped"].append(f)
                continue
            remote = f"{REMOTE}/{f}"
            try:
                remote_dir = os.path.dirname(remote)
                ensure_remote_dir(sftp, remote_dir)
                sftp.put(str(local), remote)
                results["uploaded"] += 1
            except Exception as e:
                results["failed"].append(f"{f}: {e}")
    finally:
        sftp.close()
        ssh.close()
    return results


def restart_server() -> bool:
    """Clear pycache, restart the systemd service, and wait for health."""
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    configure_ssh_host_keys(ssh)
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=15)

    try:
        commands = [
            f"find {REMOTE} -type d -name __pycache__ -exec rm -rf {{}} + 2>/dev/null",
            "systemctl restart lima-router",
        ]
        for cmd in commands:
            stdin, stdout, stderr = ssh.exec_command(cmd)
            if stdout.channel.recv_exit_status() != 0:
                detail = stderr.read().decode("utf-8", errors="replace").strip()
                print(f"restart command failed: {cmd}: {detail}")
                return False

        deadline = time.time() + HEALTH_WAIT_SECONDS
        while time.time() < deadline:
            stdin, stdout, stderr = ssh.exec_command("curl -sS -m 3 http://127.0.0.1:8080/health")
            health = stdout.read().decode("utf-8", errors="replace").strip()
            if stdout.channel.recv_exit_status() == 0 and "ok" in health:
                return True
            time.sleep(HEALTH_POLL_SECONDS)
        return False
    finally:
        ssh.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Unified LiMa deploy")
    parser.add_argument("--slice", choices=["core", "m1m5", "phase_a", "phase_b", "all"],
                        default="core", help="Which slice to deploy")
    parser.add_argument("--files", nargs="+", help="Specific files to deploy")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deployed")
    parser.add_argument("--no-restart", action="store_true", help="Skip server restart")
    args = parser.parse_args()

    files: list[str] = []

    if args.files:
        files = args.files
    elif args.slice == "all":
        files = CORE_FILES.copy()
        for slice_files in SLICE_FILES.values():
            files.extend(slice_files)
    elif args.slice == "core":
        files = CORE_FILES.copy()
    else:
        files = SLICE_FILES.get(args.slice, [])

    files = list(dict.fromkeys(files))

    print(f"Deploying {len(files)} files ({args.slice})...")
    results = deploy_files(files, dry_run=args.dry_run)

    print(f"\nResult: {results['uploaded']} uploaded, {len(results['failed'])} failed, {len(results['skipped'])} skipped")
    if results["failed"]:
        for f in results["failed"]:
            print(f"  FAIL: {f}")
        return 1

    if args.dry_run or args.no_restart:
        return 0

    if results["uploaded"] > 0:
        print("\nRestarting server...")
        ok = restart_server()
        print(f"Health: {'OK' if ok else 'FAILED'}")

        if ok:
            notify_text = format_deploy_ok(
                f"unified/{args.slice}",
                health=f"uploaded={results['uploaded']}",
            )
            print(f"\n{notify_text}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
