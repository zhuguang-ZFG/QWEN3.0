"""Tool execution gateway for dangerous or tool-backed steps.

Chains: ApprovalGate -> gateway policy -> ToolExecutor -> AuditTrail -> StepResult.
Defaults to NoopToolExecutor. Never executes without explicit gating.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

_log = logging.getLogger(__name__)

from agent_runtime.approval import ApprovalGate
from agent_runtime.contract import AgentStep, StepKind, StepResult, redact
from agent_runtime.tool_exec import NoopToolExecutor, ToolExecutor


DANGEROUS_TOOL_NAMES = frozenset({
    "deploy",
    "device_write",
    "exec",
    "hardware",
    "network_write",
    "rm",
    "shell",
    "shell_command",
    "sudo",
})


@dataclass
class ToolExecutionRequest:
    step: AgentStep
    task_id: str = ""
    worker_id: str = ""


@dataclass
class ToolExecutionDecision:
    allowed: bool
    blocked_reason: str = ""
    executor: ToolExecutor | None = None
    approval_id: str = ""
    audit_events: list[str] = field(default_factory=list)


class ToolExecutionGateway:
    """Unified gateway for dangerous step execution."""

    def __init__(
        self,
        approval_gate: ApprovalGate | None = None,
        executor: ToolExecutor | None = None,
    ) -> None:
        self.approval_gate = approval_gate or ApprovalGate(dry_run=True)
        self.executor = executor or NoopToolExecutor()

    def execute(
        self,
        step: AgentStep,
        task_id: str = "",
        worker_id: str = "",
    ) -> StepResult:
        t0 = time.time()
        audit = ["tool_request_received"]
        decision = ToolExecutionDecision(allowed=False)

        approval_result = self.approval_gate.check_step(step, task_id, worker_id)
        if approval_result is not None:
            audit.append("tool_approval_blocked")
            return self._blocked(
                step,
                decision,
                audit,
                t0,
                approval_result.blocked_reason,
                task_id,
                worker_id,
            )

        policy_reason = self._check_gateway_policy(step)
        if policy_reason:
            audit.append("tool_policy_blocked")
            return self._blocked(
                step,
                decision,
                audit,
                t0,
                policy_reason,
                task_id,
                worker_id,
            )

        audit.append("tool_executor_selected")
        decision.allowed = True
        decision.executor = self.executor
        tool_result = self.executor.run(step.command, timeout_sec=step.timeout_sec)
        audit.append("tool_execution_result")

        result = StepResult(
            step_id=step.step_id,
            ok=tool_result.ok,
            output=tool_result.output,
            error=tool_result.error,
            evidence=tool_result.evidence,
            duration_ms=(time.time() - t0) * 1000,
            blocked=not tool_result.ok,
            blocked_reason=redact(tool_result.error) if not tool_result.ok else "",
        )
        self._audit(step, task_id, worker_id, decision, audit, result)
        return result

    def _blocked(
        self,
        step: AgentStep,
        decision: ToolExecutionDecision,
        audit: list[str],
        t0: float,
        reason: str,
        task_id: str = "",
        worker_id: str = "",
    ) -> StepResult:
        result = StepResult(
            step_id=step.step_id,
            ok=False,
            blocked=True,
            blocked_reason=redact(reason),
            duration_ms=(time.time() - t0) * 1000,
            evidence=["gateway_blocked"],
        )
        self._audit(step, task_id, worker_id, decision, audit, result)
        return result

    def _check_gateway_policy(self, step: AgentStep) -> str:
        dangerous = DANGEROUS_TOOL_NAMES & set(step.allowed_tools)
        if dangerous:
            return "dangerous authority present in allowed_tools"
        if step.kind == StepKind.RUN_TESTS:
            allowed = set(step.allowed_tools)
            if allowed and not (allowed & {"run_tests", "pytest"}):
                return "run_tests step not in allowed_tools"
        return ""

    def _audit(
        self,
        step: AgentStep,
        task_id: str,
        worker_id: str,
        decision: ToolExecutionDecision,
        events: list[str],
        result: StepResult,
    ) -> None:
        try:
            from agent_runtime.audit_trail import audit_event

            for event in events:
                audit_event(
                    event,
                    task_id=task_id,
                    worker_id=worker_id,
                    approval_id=decision.approval_id,
                    detail=(
                        f"step={redact(step.step_id)} kind={step.kind.value} "
                        f"ok={result.ok} blocked={result.blocked}"
                    ),
                )
        except Exception as exc:
            _log.debug(
                "tool gateway audit skipped task=%s: %s",
                task_id,
                type(exc).__name__,
            )


def build_default_gateway(executor: ToolExecutor | None = None) -> ToolExecutionGateway:
    return ToolExecutionGateway(
        approval_gate=ApprovalGate(dry_run=True),
        executor=executor or NoopToolExecutor(),
    )
