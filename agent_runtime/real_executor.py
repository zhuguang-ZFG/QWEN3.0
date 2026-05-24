"""Real executor scaffold with multi-gate preflight and default-disabled output.

No real execution happens in this module. It defines the future execution
contract, records preflight evidence, and always returns a disabled result even
when every gate passes.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from agent_runtime.contract import AgentStep, StepKind, redact
from agent_runtime.feature_flags import (
    ExecutionFeatureFlags,
    is_network_allowed,
    is_shell_allowed,
    is_workspace_write_allowed,
    load_flags,
)
from agent_runtime.tool_exec import ToolExecutor, ToolResult


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
    check(bool(config.required_audit_refs), "audit_refs", "no required audit refs")

    kind = config.execution_kind
    if kind == "shell":
        check(
            is_shell_allowed(step.command, flags),
            "shell_allowlist",
            "command not in shell allowlist",
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
    """Scaffold executor. It never performs real shell/network/workspace work."""

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

        _audit_event(
            "real_execution_disabled",
            detail="all gates passed but executor disabled in scaffold",
        )
        return ToolResult(
            ok=False,
            error="real execution disabled in scaffold",
            evidence=["real_executor_scaffold_disabled"],
            duration_ms=(time.time() - t0) * 1000,
            executed=False,
        )

    @property
    def last_preflight(self) -> PreflightResult | None:
        return self._preflight


def _step_kind_for_execution_kind(kind: str) -> StepKind:
    if kind == "shell":
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
    except Exception:
        pass
