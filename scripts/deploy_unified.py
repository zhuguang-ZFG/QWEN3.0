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
    python deploy_unified.py --eval-smoke       # after restart, run VPS eval smoke
"""

from __future__ import annotations

import argparse
import os
import re
import shlex
import subprocess
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

HEALTH_WAIT_SECONDS = int(os.environ.get("LIMA_DEPLOY_HEALTH_WAIT_S", "180"))
HEALTH_POLL_SECONDS = 2
DEFAULT_MIN_FREE_MB = 512
DEFAULT_MIN_MEM_MB = 128

EVAL_SMOKE_TRIGGER_FILES = frozenset({
    "eval_pinned_call.py",
    "eval_call.py",
    "routes/eval_internal.py",
    "routing_executor.py",
})


def _safe_backup_label(label: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", label.strip()).strip("-._")
    return cleaned or "unified"


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc


def parse_capacity_output(output: str) -> dict[str, int]:
    capacity: dict[str, int] = {}
    for line in output.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in {"disk_free_mb", "mem_available_mb"}:
            capacity[key] = int(value.strip())
    return capacity


def capacity_result(capacity: dict[str, int], *, min_free_mb: int, min_mem_mb: int) -> dict[str, object]:
    disk_free = capacity.get("disk_free_mb", -1)
    mem_available = capacity.get("mem_available_mb", -1)
    if disk_free < min_free_mb:
        return {
            "ok": False,
            "reason": f"disk free {disk_free}MB below required {min_free_mb}MB",
        }
    if mem_available < min_mem_mb:
        return {
            "ok": False,
            "reason": f"memory available {mem_available}MB below required {min_mem_mb}MB",
        }
    return {"ok": True, "reason": "capacity ok"}


def _connect_ssh() -> paramiko.SSHClient:
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    configure_ssh_host_keys(ssh)
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=15)
    return ssh


def _exec(ssh: paramiko.SSHClient, command: str) -> tuple[int, str, str]:
    _stdin, stdout, stderr = ssh.exec_command(command)
    code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    return code, out, err


def check_remote_capacity(ssh: paramiko.SSHClient) -> dict[str, int]:
    command = (
        "set -eu; "
        f"disk=$(df -Pm {shlex.quote(REMOTE)} | awk 'NR==2 {{print $4}}'); "
        "mem=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo); "
        'echo "disk_free_mb=$disk"; '
        'echo "mem_available_mb=$mem"'
    )
    code, out, err = _exec(ssh, command)
    if code != 0:
        raise RuntimeError(f"remote capacity check failed: {err or out}")
    capacity = parse_capacity_output(out)
    if "disk_free_mb" not in capacity or "mem_available_mb" not in capacity:
        raise RuntimeError(f"remote capacity check returned incomplete data: {out}")
    return capacity


def create_remote_backup(ssh: paramiko.SSHClient, files: list[str], *, label: str) -> str:
    safe_label = _safe_backup_label(label)
    backup_dir = f"{REMOTE}/backups/{safe_label}-{time.strftime('%Y%m%d_%H%M%S')}"
    backup_file = f"{backup_dir}/runtime-before.tgz"
    quoted_files = " ".join(shlex.quote(f) for f in files)
    command = (
        "set -eu; "
        f"mkdir -p {shlex.quote(backup_dir)}; "
        f"cd {shlex.quote(REMOTE)}; "
        f"tar --ignore-failed-read -czf {shlex.quote(backup_file)} {quoted_files}; "
        f"echo {shlex.quote(backup_file)}"
    )
    code, out, err = _exec(ssh, command)
    if code != 0:
        raise RuntimeError(f"remote backup failed: {err or out}")
    return out.splitlines()[-1].strip()


def prepare_remote_deploy(files: list[str], *, label: str) -> dict[str, object]:
    min_free_mb = _env_int("LIMA_DEPLOY_MIN_FREE_MB", DEFAULT_MIN_FREE_MB)
    min_mem_mb = _env_int("LIMA_DEPLOY_MIN_MEM_MB", DEFAULT_MIN_MEM_MB)
    ssh = _connect_ssh()
    try:
        capacity = check_remote_capacity(ssh)
        result = capacity_result(
            capacity,
            min_free_mb=min_free_mb,
            min_mem_mb=min_mem_mb,
        )
        if not result["ok"]:
            return {"ok": False, "capacity": capacity, "reason": result["reason"]}
        backup_path = create_remote_backup(ssh, files, label=label)
        return {
            "ok": True,
            "capacity": capacity,
            "backup_path": backup_path,
        }
    finally:
        ssh.close()


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


def _should_run_eval_smoke(files: list[str], force: bool) -> bool:
    if force:
        return True
    normalized = {f.replace("\\", "/") for f in files}
    return bool(normalized & EVAL_SMOKE_TRIGGER_FILES)


def run_eval_smoke() -> bool:
    """Run remote VPS eval smoke (pinned + FRP paths)."""
    script = Path(__file__).resolve().parent / "vps_eval_smoke_remote.py"
    if not script.is_file():
        print(f"  eval smoke: missing {script.name}")
        return False
    print("\n=== VPS eval smoke ===")
    try:
        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(script.parent.parent),
            check=False,
        )
    except OSError as exc:
        print(f"  eval smoke failed to start: {type(exc).__name__}: {exc}")
        return False
    if result.returncode == 0:
        print("  eval smoke: OK")
        return True
    print(f"  eval smoke: FAILED (exit {result.returncode})")
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Unified LiMa deploy")
    parser.add_argument("--slice", choices=["core", "m1m5", "phase_a", "phase_b", "all"],
                        default="core", help="Which slice to deploy")
    parser.add_argument("--files", nargs="+", help="Specific files to deploy")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deployed")
    parser.add_argument("--no-restart", action="store_true", help="Skip server restart")
    parser.add_argument(
        "--eval-smoke",
        action="store_true",
        help="After successful health check, run scripts/vps_eval_smoke_remote.py",
    )
    parser.add_argument(
        "--no-eval-smoke",
        action="store_true",
        help="Skip auto eval smoke even when eval/routing files were deployed",
    )
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
        print(f"Health: {'OK' if ok else 'FAILED'} (wait up to {HEALTH_WAIT_SECONDS}s)")

        if not ok:
            return 1

        notify_text = format_deploy_ok(
            f"unified/{args.slice}",
            health=f"uploaded={results['uploaded']}",
        )
        print(f"\n{notify_text}")

        run_smoke = _should_run_eval_smoke(files, args.eval_smoke) and not args.no_eval_smoke
        if run_smoke and not run_eval_smoke():
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
