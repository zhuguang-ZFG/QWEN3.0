#!/usr/bin/env python3
"""Full VPS sync — dynamically discovers and uploads ALL Python runtime files.

Uses git to find tracked .py files (not tests, not scripts unless needed).
This eliminates the "hardcoded list" class of bugs.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import paramiko

SERVER = "47.112.162.80"
REMOTE = "/opt/lima-router"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))

# Directories to sync EVERY tracked .py file from
SYNC_DIRS = [
    "routes", "device_gateway", "session_memory", "agent_runtime",
    "lima_mcp", "observability", "context_pipeline", "search_gateway",
    "tool_gateway", "channel_gateway", "converters", "user_identity",
    "mastery_loop", "github_webhook", "gitee_webhook",
]

# Individual tracked files to sync
SYNC_FILES = [
    "server.py", "routing_engine.py", "smart_router.py", "http_caller.py",
    "server_lifespan.py", "server_bootstrap.py", "server_context.py",
    "backends.py", "backends_registry.py", "backends_constants.py",
    "router_v3.py", "route_scorer.py", "route_post_process.py",
    "budget_manager.py", "health_tracker.py", "identity_guard.py",
    "semantic_cache.py", "speculative.py", "sticky_session.py",
    "skills_injector.py", "response_builder.py", "response_cleaner.py",
    "routing_classifier.py", "routing_executor.py", "routing_selector.py",
    "chat_models.py", "vision_handler.py", "http_body_limit.py",
    "access_guard.py", "probe_loop.py", "runtime_topology.py",
    "key_pool.py", "backend_admission_store.py",
    "code_orchestrator.py", "code_orchestrator_context.py",
    "eval_pool_gate.py", "eval_topology.py", "eval_call.py",
    "periodic_coding_eval.py", "oldllm_diag.py", "oldllm_sync.py",
    "lima_context.py", "streaming.py",
    "telegram_async.py", "telegram_archive.py", "telegram_bot.py",
    "telegram_notify.py", "telegram_b2b.py",
    "health_recorder.py", "health_summary.py", "worker_daemon.py",
    "requirements_server.txt", "litestream.yml", "pyrightconfig.json",
    "scripts/ci_notify.py", "scripts/run_pytest_ci.py",
    "scripts/run_pyright.py", "scripts/run_deptry.py",
]


def _discover_files() -> list[str]:
    """Use git ls-files to find ALL tracked Python files in sync dirs."""
    base = Path(__file__).resolve().parent.parent
    files = list(SYNC_FILES)
    try:
        result = subprocess.run(
            ["git", "ls-files", "--", "*.py"],
            cwd=base, capture_output=True, text=True, check=True,
        )
        for line in result.stdout.splitlines():
            path = line.strip()
            if not path:
                continue
            # Skip tests, local scripts, and non-runtime files
            if path.startswith("tests/"):
                continue
            if path.startswith("scripts/") and path not in SYNC_FILES:
                continue
            if path in files:
                continue
            # Include if in a sync dir or is a top-level .py
            for d in SYNC_DIRS:
                if path.startswith(d + "/"):
                    files.append(path)
                    break
            else:
                # Top-level .py files
                if "/" not in path and path.endswith(".py"):
                    files.append(path)
    except Exception:
        pass  # fall back to hardcoded list
    return files


def main() -> int:
    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    base = Path(__file__).resolve().parent.parent
    files = _discover_files()
    print(f"Discovered {len(files)} files to sync")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)

    missing: list[str] = []
    failed: list[str] = []

    sftp = ssh.open_sftp()
    for rel in files:
        local = base / rel
        if not local.is_file():
            missing.append(rel)
            continue
        remote = f"{REMOTE}/{rel.replace(chr(92), '/')}"
        remote_dir = os.path.dirname(remote)
        try:
            sftp.put(str(local), remote)
        except FileNotFoundError:
            # Create remote dir and retry
            try:
                ssh.exec_command(f"mkdir -p {remote_dir}")
                sftp.put(str(local), remote)
            except Exception:
                failed.append(rel)
        except Exception:
            failed.append(rel)
    sftp.close()

    if missing:
        print(f"LOCAL MISSING ({len(missing)}):")
        for m in missing[:5]:
            print(f"  {m}")

    if failed:
        print(f"UPLOAD FAILED ({len(failed)}):")
        for f in failed[:5]:
            print(f"  {f}")

    if not missing and not failed:
        print(f"All {len(files)} files synced to VPS")

    # Restart and verify
    ssh.exec_command("systemctl daemon-reload 2>/dev/null; systemctl restart lima-router")
    time.sleep(10)
    _i, o, _e = ssh.exec_command("systemctl is-active lima-router")
    status = o.read().decode().strip()
    _i, o, _e = ssh.exec_command("curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/health")
    health_code = o.read().decode().strip()
    print(f"VPS: {status} | /health={health_code}")

    ssh.close()
    return 0 if status == "active" and health_code == "200" else 1


if __name__ == "__main__":
    raise SystemExit(main())
