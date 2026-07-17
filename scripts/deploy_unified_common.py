"""Shared constants and low-level helpers for the unified VPS deploy."""

from __future__ import annotations

import dataclasses
import re
import subprocess
import sys
from pathlib import Path
from pathlib import PureWindowsPath

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import deploy_config


@dataclasses.dataclass(frozen=True)
class DeployTarget:
    """Connection details for a single VPS deploy target."""

    name: str
    host: str
    remote_path: str
    user: str
    password: str = dataclasses.field(repr=False)
    key_path: str


TARGET_ALIYUN = "aliyun"
TARGET_JDCLOUD = "jdcloud"
TARGET_DEFAULT = TARGET_JDCLOUD


def get_deploy_target(target: str | None = None) -> DeployTarget:
    """Resolve a target name into connection credentials.

    Defaults to JDCloud because the production entry (chat.donglicao.com)
    is served through the JDCloud node. Use ``aliyun`` for the legacy pilot node.
    """
    name = (target or deploy_config.deploy_target()).lower().strip()
    key_path = deploy_config.expanded_key_path()
    if name == TARGET_ALIYUN:
        return DeployTarget(
            name=TARGET_ALIYUN,
            host=deploy_config.ALIYUN_SERVER,
            remote_path=deploy_config.REMOTE_PATH,
            user="root",
            password=deploy_config.aliyun_password(),
            key_path=key_path,
        )
    if name == TARGET_JDCLOUD:
        return DeployTarget(
            name=TARGET_JDCLOUD,
            host=deploy_config.JDCLOUD_SERVER,
            remote_path=deploy_config.REMOTE_PATH,
            user=deploy_config.JDCLOUD_USER,
            password=deploy_config.jdcloud_password(),
            key_path=key_path,
        )
    raise ValueError(f"unknown deploy target: {target!r}")


CORE_FILES = [
    "access_guard.py",
    "app_status_ws_connections.py",
    "app_status_ws_ticket.py",
    "async_utils.py",
    "dashscope_image_client.py",
    "device_protocol_registry.py",
    "requirements_server.txt",
    "server_dlc.py",
    "rate_limiter.py",
    "runtime_env.py",
    "voice_app_ws_ticket.py",
    "voice_ws_connections.py",
    "ws_ticket.py",
]

# Post-P5 slimdown: only directories that still exist on disk and are reachable
# from server_dlc.py. device_voice/ is deployed via --files (not in CORE_DIRS).
# Deleted subsystems (context_pipeline, session_memory, code_context,
# backends_registry, channel_retirement) are no longer deployed.
CORE_DIRS = [
    "routes",
    "device_gateway",
    "device_ledger",
    "device_memory",
    "device_intelligence",
    "device_logic",
    "device_policy",
    "device_workflow",
    "device_voice",
    "device_artifacts",
    "dlc_api",
    "dlc_core",
    "dlc_mcp",
    "integrations",
    "observability",
    "xiaozhi_drawing",
    "config",
    "common",
    "client_keys",
]

# P4/P5 瘦身后旧 phase_a/phase_b 切片引用的模块（routing_engine/routing_selector/
# context_pipeline/route_post_process）均已物理删除。仅保留 core/all/files 部署路径。
SLICE_FILES: dict[str, list[str]] = {}

HEALTH_WAIT_SECONDS = deploy_config.deploy_health_wait_s()
HEALTH_POLL_SECONDS = 3
HEALTH_GRACE_AFTER_RESTART_S = deploy_config.deploy_health_grace_s()
READY_WAIT_SECONDS = 60
READY_POLL_SECONDS = 3
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
    "htmlcov",
    "infra",
    "lima_mcp_stdio",
    "packages",
    "reference",
    "scripts/archive",
    "tests",
    "__pycache__",
}


def _normalize_deploy_path(raw: str) -> str:
    """Return one safe repository-relative POSIX path or raise ValueError."""
    if not raw or any(ord(char) < 32 for char in raw):
        raise ValueError(f"unsafe deploy path: {raw!r}")
    if raw.startswith(("/", "\\")) or PureWindowsPath(raw).drive:
        raise ValueError(f"absolute deploy path: {raw!r}")
    normalized = raw.replace("\\", "/")
    parts = normalized.split("/")
    if any(part in {"", ".", ".."} or part.startswith(".") for part in parts):
        raise ValueError(f"unsafe deploy path: {raw!r}")
    if any(normalized == item or normalized.startswith(f"{item}/") for item in _DEPLOY_EXCLUDES):
        raise ValueError(f"excluded deploy path: {raw!r}")
    if "__pycache__" in parts or normalized.endswith((".pyc", ".pyo")):
        raise ValueError(f"generated deploy path: {raw!r}")
    return normalized


def _is_runtime_path(rel: str) -> bool:
    """Return True for files that belong to the runtime deploy manifest."""
    try:
        _normalize_deploy_path(rel)
    except ValueError:
        return False
    return True


def _git_tracked_files(project_root: Path) -> list[str]:
    """Return repository-tracked files; deployment never consumes local ignored data."""
    completed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=project_root,
        check=True,
        capture_output=True,
    )
    return [item.decode("utf-8").replace("\\", "/") for item in completed.stdout.split(b"\0") if item]


def _is_core_path(rel: str) -> bool:
    try:
        normalized = _normalize_deploy_path(rel)
    except ValueError:
        return False
    return normalized in CORE_FILES or any(normalized.startswith(f"{directory}/") for directory in CORE_DIRS)


def _git_diff_files(project_root: Path, before: str, after: str, *, diff_filter: str) -> list[str]:
    """Return NUL-delimited changed paths without rename collapsing."""
    completed = subprocess.run(
        ["git", "diff", "--no-renames", "--name-only", "-z", f"--diff-filter={diff_filter}", before, after],
        cwd=project_root,
        check=True,
        capture_output=True,
    )
    return [item.decode("utf-8").replace("\\", "/") for item in completed.stdout.split(b"\0") if item]


def collect_git_range(project_root: Path, before: str, after: str) -> tuple[list[str], list[str]]:
    """Collect validated core uploads and removals for one push range."""
    tracked = set(_git_tracked_files(project_root))
    uploads = _git_diff_files(project_root, before, after, diff_filter="ACMRT")
    removals = _git_diff_files(project_root, before, after, diff_filter="D")
    uploads = [path for path in uploads if path in tracked and _is_core_path(path)]
    removals = [path for path in removals if _is_core_path(path)]
    return sorted(set(uploads)), sorted(set(removals))


def _collect_core_files(project_root: Path) -> list[str]:
    return sorted(rel for rel in _git_tracked_files(project_root) if _is_runtime_path(rel) and _is_core_path(rel))


def _collect_runtime_files(project_root: Path) -> list[str]:
    """Keep the legacy ``all`` slice constrained to the production runtime allowlist."""
    return _collect_core_files(project_root)


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
