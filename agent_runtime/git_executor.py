"""Restricted git executor with whitelisted subcommands.

Only allows safe git operations: status, diff, log, commit, branch, show.
Network operations (push, pull, fetch) are blocked here.
All execution gated behind LIMA_DRY_RUN=0 + LIMA_ALLOW_SHELL=1.
"""

from __future__ import annotations

import logging
import time

from agent_runtime.contract import redact
from agent_runtime.feature_flags import ExecutionFeatureFlags
from agent_runtime.shell_executor import shell_execute
from agent_runtime.tool_exec import ToolResult

_log = logging.getLogger(__name__)

_ALLOWED_GIT_SUBCOMMANDS: frozenset[str] = frozenset({
    "status",
    "diff",
    "log",
    "commit",
    "branch",
    "show",
    "rev-parse",
    "describe",
    "shortlog",
    "blame",
})

_BLOCKED_GIT_SUBCOMMANDS: frozenset[str] = frozenset({
    "push",
    "pull",
    "fetch",
    "remote",
    "clone",
    "submodule",
})


def git_execute(
    command: str,
    *,
    flags: ExecutionFeatureFlags,
    cwd: str | None = None,
    timeout_sec: float = 15.0,
) -> ToolResult:
    t0 = time.time()

    subcommand = _extract_git_subcommand(command)
    if not subcommand:
        return ToolResult(
            ok=False,
            error="could not parse git subcommand",
            evidence=["git_parse_error"],
            duration_ms=(time.time() - t0) * 1000,
            executed=False,
        )

    if subcommand in _BLOCKED_GIT_SUBCOMMANDS:
        return ToolResult(
            ok=False,
            error=f"git {subcommand} is blocked (network operation)",
            evidence=[f"git_blocked_{subcommand}"],
            duration_ms=(time.time() - t0) * 1000,
            executed=False,
        )

    if subcommand not in _ALLOWED_GIT_SUBCOMMANDS:
        return ToolResult(
            ok=False,
            error=f"git {subcommand} is not in allowlist",
            evidence=[f"git_not_allowed_{subcommand}"],
            duration_ms=(time.time() - t0) * 1000,
            executed=False,
        )

    result = shell_execute(
        command,
        flags=flags,
        cwd=cwd,
        timeout_sec=min(timeout_sec, 15.0),
    )

    result.evidence = [f"git_{subcommand}"] + result.evidence
    return result


def _extract_git_subcommand(command: str) -> str:
    parts = command.strip().split()
    if not parts or parts[0] != "git":
        return ""
    if len(parts) < 2:
        return ""
    sub = parts[1].lstrip("-")
    return sub
