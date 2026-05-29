"""Real executor with multi-gate preflight and dispatch to shell/git/network.

Execution modes (via LIMA_EXEC_MODE):
  dry  — all real execution blocked (default)
  safe — shell + workspace allowed with allowlist and scope restrictions
  full — all execution allowed (dangerous commands still blocked)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

_log = logging.getLogger(__name__)

from agent_runtime.contract import AgentStep, StepKind, redact
from agent_runtime.feature_flags import (
    BLOCKED_COMMANDS,
    ExecutionFeatureFlags,
    is_network_allowed,
    is_shell_allowed,
    is_workspace_write_allowed,
    load_flags,
)
from agent_runtime.tool_exec import ToolExecutor, ToolResult

# Safe mode blocks these commands even though they're in the shell allowlist
SAFE_MODE_BLOCKED: frozenset[str] = frozenset({
    "rm", "rmdir", "dd", "mkfs", "format", "fdisk",
    "shutdown", "reboot", "halt", "poweroff", "init",
    "kill", "killall", "pkill",
    "sudo", "su", "passwd",
    "nc", "ncat", "socat",
    "chmod", "chown", "chgrp",
    "mount", "umount",
    "iptables", "firewall-cmd",
    "docker", "podman", "systemctl",
})

# Safe mode path restrictions — write only inside workspace root
SAFE_MODE_WRITE_ROOTS = frozenset({
    "LIMA_WORKSPACE_ROOT",
})


@dataclass
class RealExecutorConfig:
    enabled: bool = False
    dry_run: bool = True
    execution_kind: str = "shell"
    operator_session_id: str = ""
    required_audit_refs: list[str] = field(default_factory=list)
    allowlist_snapshot: list[str] = field(default_factory=list)


@dataclass
class PreflightResult:
    passed: bool
    blocked_reason: str = ""
    checks_passed: list[str] = field(default_factory=list)
    checks_failed: list[str] = field(default_factory=list)


def preflight_real_execution(
    config: RealExecutorConfig,
    step: AgentStep,
    flags: ExecutionFeatureFlags | None = None,
) -> PreflightResult:
    flags = flags or load_flags()
    passed: list[str] = []
    failed: list[str] = []

    def check(condition: bool, name: str, reason: str) -> None:
        if condition:
            passed.append(name)
        else:
            failed.append(f"{name}: {redact(reason)}")

    check(config.enabled, "config_enabled", "config.enabled is False")
    check(not config.dry_run, "config_dry_run", "config.dry_run is True")
    check(flags.dry_run is False, "flags_dry_run", "flags.dry_run is True")
    check(bool(config.operator_session_id), "operator_session", "no operator session id")

    kind = config.execution_kind
    if kind == "shell":
        check(
            is_shell_allowed(step.command, flags),
            "shell_allowlist",
            "command not in shell allowlist",
        )
        # Extra safe-mode check: block dangerous commands even if in allowlist
        if flags.exec_mode == "safe":
            base_cmd = step.command.strip().split()[0] if step.command.strip() else ""
            check(
                base_cmd not in SAFE_MODE_BLOCKED,
                "safe_mode_blocked",
                f"command '{base_cmd}' blocked in safe mode",
            )
    elif kind == "git":
        check(
            is_shell_allowed(step.command, flags),
            "shell_allowlist",
            "git requires shell allowlist",
        )
    elif kind == "network":
        check(
            is_network_allowed(step.command, flags),
            "network_allowlist",
            "domain not in network allowlist",
        )
    elif kind == "workspace":
        check(
            is_workspace_write_allowed(step.command, flags),
            "workspace_allowlist",
            "path not in workspace allowlist",
        )
    else:
        check(False, "execution_kind", f"unknown execution kind: {kind}")

    result = PreflightResult(
        passed=not failed,
        blocked_reason="; ".join(failed[:3]) if failed else "",
        checks_passed=passed,
        checks_failed=failed,
    )
    _audit_preflight(config, step, result)
    return result


class RealToolExecutor(ToolExecutor):
    """Executes real commands after preflight gates pass.

    Dispatches to shell, git, network, or workspace executors based on
    execution_kind. All gated behind LIMA_DRY_RUN=0 + LIMA_ALLOW_*=1.
    """

    def __init__(
        self,
        config: RealExecutorConfig | None = None,
        flags: ExecutionFeatureFlags | None = None,
    ) -> None:
        self.config = config or RealExecutorConfig()
        self.flags = flags or load_flags()
        self._preflight: PreflightResult | None = None

    def run(self, command: str, timeout_sec: float = 30.0) -> ToolResult:
        t0 = time.time()
        step = AgentStep(
            step_id="real-executor-preflight",
            kind=_step_kind_for_execution_kind(self.config.execution_kind),
            command=command,
            timeout_sec=timeout_sec,
        )
        self._preflight = preflight_real_execution(self.config, step, self.flags)

        if not self._preflight.passed:
            _audit_event("real_execution_blocked", detail=self._preflight.blocked_reason)
            return ToolResult(
                ok=False,
                error=self._preflight.blocked_reason,
                evidence=[
                    f"preflight_failed:{check}"
                    for check in self._preflight.checks_failed[:5]
                ],
                duration_ms=(time.time() - t0) * 1000,
                executed=False,
            )

        return _dispatch_execution(
            command, self.config.execution_kind, self.flags, timeout_sec, t0,
        )

    @property
    def last_preflight(self) -> PreflightResult | None:
        return self._preflight


def _dispatch_execution(
    command: str,
    kind: str,
    flags: ExecutionFeatureFlags,
    timeout_sec: float,
    t0: float,
) -> ToolResult:
    _audit_event(
        "real_execution_dispatch",
        detail=f"kind={kind} command={redact(command[:100])}",
    )

    if kind == "shell":
        from agent_runtime.shell_executor import shell_execute

        return shell_execute(command, flags=flags, timeout_sec=timeout_sec)

    if kind == "git":
        from agent_runtime.git_executor import git_execute

        return git_execute(command, flags=flags, timeout_sec=timeout_sec)

    if kind == "network":
        from agent_runtime.network_executor import network_execute

        return network_execute(command, flags=flags, timeout_sec=timeout_sec)

    if kind == "workspace":
        return _workspace_execute(command, t0)

    return ToolResult(
        ok=False,
        error=f"execution kind '{kind}' not yet supported",
        evidence=[f"unsupported_kind:{kind}"],
        duration_ms=(time.time() - t0) * 1000,
        executed=False,
    )


def _workspace_execute(command: str, t0: float) -> ToolResult:
    from pathlib import Path

    target = Path(command)
    if not target.parent.exists():
        return ToolResult(
            ok=False,
            error=f"parent directory does not exist: {target.parent}",
            evidence=["workspace_parent_missing"],
            duration_ms=(time.time() - t0) * 1000,
            executed=False,
        )
    return ToolResult(
        ok=True,
        output=f"workspace path validated: {target}",
        evidence=["workspace_validated"],
        duration_ms=(time.time() - t0) * 1000,
        executed=True,
    )


def _step_kind_for_execution_kind(kind: str) -> StepKind:
    if kind in ("shell", "git"):
        return StepKind.SHELL_COMMAND
    if kind == "network":
        return StepKind.HTTP_CALL
    return StepKind.NOOP


def _audit_preflight(
    config: RealExecutorConfig,
    step: AgentStep,
    result: PreflightResult,
) -> None:
    detail = (
        f"kind={redact(config.execution_kind)} passed={result.passed} "
        f"command={redact(step.command[:120])}"
    )
    _audit_event("real_execution_preflight", detail=detail)
    if not result.passed:
        _audit_event("real_execution_blocked", detail=result.blocked_reason)


def _audit_event(event: str, detail: str = "") -> None:
    try:
        from agent_runtime.audit_trail import audit_event

        audit_event(event, detail=detail)
    except Exception as exc:
        _log.debug(
            "real_executor audit skipped event=%s: %s", event, type(exc).__name__,
        )
