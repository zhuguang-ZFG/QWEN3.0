"""Shared constants and low-level helpers for the unified VPS deploy."""

from __future__ import annotations

import os
import re
import shlex
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.deploy_common import (
    SERVER,
    REMOTE,
    KEY,
    configure_ssh_host_keys,
)

import paramiko


CORE_FILES = [
    "server.py",
    "routing_engine.py",
    "routing_selector/__init__.py",
    "router_v3/__init__.py",
    "routing_intent.py",
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
    "code_context",

    "observability",
    "device_ledger",
    "device_memory",
    "device_gateway",
    "device_voice",
    "backends_registry",
    "channel_retirement",
]

SLICE_FILES = {
    "phase_a": [
        "routing_engine.py",
        "routing_selector/__init__.py",
    ],
    "phase_b": [
        "context_pipeline/response_validator.py",
        "context_pipeline/auto_indexer.py",
        "route_post_process.py",
    ],
}

from config import deploy_config

HEALTH_WAIT_SECONDS = deploy_config.deploy_health_wait_s()
HEALTH_POLL_SECONDS = 3
HEALTH_GRACE_AFTER_RESTART_S = deploy_config.deploy_health_grace_s()
DEFAULT_MIN_FREE_MB = 512
DEFAULT_MIN_MEM_MB = 128

# Directories/files that should never be deployed from this script.
_DEPLOY_EXCLUDES = {
    ".git",
    ".venv310",
    ".pytest_cache",
    ".ruff_cache",
    ".codegraph",
    ".lima-data",
    ".agent",
    ".codebuddy",
    ".continue",
    ".gemini",
    ".github",
    ".hypothesis",
    ".kimi-code",
    ".kiro",
    ".omc",
    ".omk",
    ".omx",
    ".opencode",
    ".pnpm-store",
    ".qoder",
    ".roo",
    ".trae",
    ".windsurf",
    "andrej-karpathy-skills",
    "data",
    "docs",
    "donglicao-site",
    "donglicao-site-backup",
    "donglicao-site-v2",
    "docs-site",
    "chat-web",
    "esp32S_XYZ",
    "infra",
    "lima_mcp_stdio",
    "packages",
    "reference",
    "scripts/archive",
    "tests",
    "__pycache__",
}


def _is_runtime_path(rel: str) -> bool:
    """Return True for files that belong to the runtime deploy manifest."""
    if not rel:
        return False
    parts = rel.replace("\\", "/").split("/")
    if any(part in _DEPLOY_EXCLUDES or part.startswith(".") for part in parts):
        return False
    if "/__pycache__/" in rel or rel.endswith(".pyc") or rel.endswith(".pyo"):
        return False
    return True


def _collect_runtime_files(project_root: Path) -> list[str]:
    """Collect all runtime files for a full-repo deploy (excluding tests/docs/data)."""
    files: list[str] = []
    for root, dirs, filenames in os.walk(project_root):
        # Prune excluded directories in-place to avoid walking them.
        dirs[:] = [d for d in dirs if d not in _DEPLOY_EXCLUDES and not d.startswith(".")]
        for name in filenames:
            local_path = Path(root) / name
            rel = local_path.relative_to(project_root).as_posix()
            if not _is_runtime_path(rel):
                continue
            # Skip obvious non-runtime artifacts.
            if name.endswith((".log", ".db", ".sqlite3", ".tgz", ".tar.gz", ".zip", ".tmp")):
                continue
            files.append(rel)
    return sorted(set(files))


def _safe_backup_label(label: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", label.strip()).strip("-._")
    return cleaned or "unified"


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
    password = deploy_config.deploy_pass()
    try:
        ssh.connect(SERVER, username="root", key_filename=KEY, timeout=15)
    except paramiko.SSHException:
        if not password:
            raise
        ssh.connect(SERVER, username="root", password=password, timeout=15)
    return ssh


def _exec(ssh: paramiko.SSHClient, command: str) -> tuple[int, str, str]:
    _stdin, stdout, stderr = ssh.exec_command(command)
    code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    return code, out, err
