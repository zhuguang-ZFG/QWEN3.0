"""Real execution feature flags with env/config gates and audit pre-check.

Three execution modes via LIMA_EXEC_MODE:
  dry  — all real execution disabled (default, safest)
  safe — shell + workspace write enabled with allowlist + scope restrictions
  full — all execution enabled (requires explicit opt-in)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

_log = logging.getLogger(__name__)


SHELL_ALLOWLIST: frozenset[str] = frozenset({
    "pytest", "echo", "python", "git",
    "ls", "cat", "grep", "find", "sed", "head", "tail",
    "wc", "sort", "diff", "pip", "python3", "python3.10",
    "mkdir", "cp", "mv", "touch", "chmod",
    "curl", "wget", "jq", "env", "which",
})
NETWORK_DOMAIN_ALLOWLIST: frozenset[str] = frozenset()
WORKSPACE_ALLOWLIST: frozenset[str] = frozenset()

# Dangerous command patterns — always blocked even in full mode
BLOCKED_COMMANDS: frozenset[str] = frozenset({
    "rm", "rmdir", "dd", "mkfs", "format",
    "shutdown", "reboot", "halt", "poweroff",
    "kill", "killall", "pkill",
    "sudo", "su", "passwd",
    "nc", "ncat", "socat",
})

EXEC_MODES = frozenset({"dry", "safe", "full"})


@dataclass
class ExecutionFeatureFlags:
    allow_shell: bool = False
    allow_network: bool = False
    allow_workspace_write: bool = False
    dry_run: bool = True
    exec_mode: str = "dry"
    shell_allowlist: frozenset[str] = frozenset()
    network_domain_allowlist: frozenset[str] = frozenset()
    workspace_allowlist: frozenset[str] = frozenset()

    @property
    def any_real_execution(self) -> bool:
        return self.allow_shell or self.allow_network or self.allow_workspace_write


def load_flags() -> ExecutionFeatureFlags:
    raw_mode = os.environ.get("LIMA_EXEC_MODE", "").strip().lower()
    exec_mode = raw_mode if raw_mode in EXEC_MODES else "dry"
    mode_explicitly_set = raw_mode in EXEC_MODES

    # Legacy env vars still override when exec_mode is not explicitly set
    explicit_shell = os.environ.get("LIMA_ALLOW_SHELL", "") == "1"
    explicit_network = os.environ.get("LIMA_ALLOW_NETWORK", "") == "1"
    explicit_workspace = os.environ.get("LIMA_ALLOW_WORKSPACE_WRITE", "") == "1"
    explicit_dry = os.environ.get("LIMA_DRY_RUN", "")

    if exec_mode == "safe":
        allow_shell = True
        allow_network = False
        allow_workspace_write = True
        dry_run = False
    elif exec_mode == "full":
        allow_shell = True
        allow_network = True
        allow_workspace_write = True
        dry_run = False
    elif mode_explicitly_set:
        # exec_mode="dry" explicitly set → always dry run
        allow_shell = False
        allow_network = False
        allow_workspace_write = False
        dry_run = True
    else:
        # Legacy path: LIMA_EXEC_MODE not set, honor LIMA_DRY_RUN + LIMA_ALLOW_*
        allow_shell = explicit_shell
        allow_network = explicit_network
        allow_workspace_write = explicit_workspace
        dry_run = explicit_dry != "0" if explicit_dry else True

    workspace_root = os.environ.get("LIMA_WORKSPACE_ROOT", os.getcwd())

    return ExecutionFeatureFlags(
        allow_shell=allow_shell,
        allow_network=allow_network,
        allow_workspace_write=allow_workspace_write,
        dry_run=dry_run,
        exec_mode=exec_mode,
        shell_allowlist=_parse_allowlist("LIMA_SHELL_ALLOWLIST", SHELL_ALLOWLIST),
        network_domain_allowlist=_parse_allowlist("LIMA_NETWORK_DOMAIN_ALLOWLIST"),
        workspace_allowlist=_parse_allowlist(
            "LIMA_WORKSPACE_ALLOWLIST",
            frozenset({workspace_root}),
        ),
    )


def is_shell_allowed(command: str, flags: ExecutionFeatureFlags) -> bool:
    if flags.dry_run or not flags.allow_shell:
        return False
    base = command.strip().split()[0] if command.strip() else ""
    if not base:
        return False
    # Always block dangerous commands regardless of mode
    if base in BLOCKED_COMMANDS:
        return False
    # Block sudo prefix patterns like "sudo rm ..."
    stripped = command.strip()
    if stripped.startswith("sudo ") or stripped.startswith("su "):
        return False
    return base in flags.shell_allowlist


def is_network_allowed(url: str, flags: ExecutionFeatureFlags) -> bool:
    if flags.dry_run or not flags.allow_network:
        return False
    if not flags.network_domain_allowlist:
        return False
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        host = parsed.hostname or ""
        return any(_host_matches(host, domain) for domain in flags.network_domain_allowlist)
    except Exception:
        return False


def is_workspace_write_allowed(path: str, flags: ExecutionFeatureFlags) -> bool:
    if flags.dry_run or not flags.allow_workspace_write:
        return False
    if not flags.workspace_allowlist:
        return False
    target = Path(path).resolve()
    for root in flags.workspace_allowlist:
        try:
            root_path = Path(root).resolve()
        except OSError:
            continue
        if root_path in (target, *target.parents):
            return True
    return False


def preflight_audit_check(task_id: str = "", worker_id: str = "") -> dict:
    flags = load_flags()
    result = {
        "allowed": not flags.dry_run and flags.any_real_execution,
        "dry_run": flags.dry_run,
        "shell": flags.allow_shell,
        "network": flags.allow_network,
        "workspace_write": flags.allow_workspace_write,
        "task_id": task_id,
        "worker_id": worker_id,
    }
    try:
        from agent_runtime.audit_trail import audit_event

        audit_event(
            "feature_flag_preflight",
            task_id=task_id,
            worker_id=worker_id,
            detail=str(result),
        )
    except Exception as exc:
        _log.debug(
            "feature_flag_preflight audit skipped task=%s: %s",
            task_id,
            type(exc).__name__,
        )
    return result


def _parse_allowlist(
    env_name: str,
    default: frozenset[str] | None = None,
) -> frozenset[str]:
    raw = os.environ.get(env_name, "")
    if not raw:
        return default or frozenset()
    return frozenset(item.strip() for item in raw.split(",") if item.strip())


def _host_matches(host: str, domain: str) -> bool:
    host = host.lower().rstrip(".")
    domain = domain.lower().rstrip(".")
    return host == domain or host.endswith(f".{domain}")
