"""Safe dry-run executor for AgentSteps.

Default mode is dry-run. The executor does not execute shell commands, perform
network calls, or write to the workspace.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from agent_runtime.contract import (
    AgentRunResult,
    AgentRunStatus,
    AgentStep,
    AgentTask,
    StepKind,
    StepResult,
    redact,
)
from agent_runtime.planner import plan_task
from agent_runtime.tool_policy import check_step_policy
from agent_runtime.store import AgentRunStore
from agent_runtime.approval import ApprovalGate
from agent_runtime.tool_gateway_adapter import ToolExecutionGateway


@dataclass
class RuntimeHooks:
    """Optional read-only hooks for custom step handling."""

    on_retrieve_context: Callable[[str], object] | None = None


class AgentRuntime:
    """Safe agent task executor. Default dry-run, no shell, no network."""

    def __init__(self, dry_run: bool = True, hooks: RuntimeHooks | None = None,
                 store: AgentRunStore | None = None,
                 approval_gate: ApprovalGate | None = None,
                 tool_gateway: ToolExecutionGateway | None = None) -> None:
        self.dry_run = dry_run
        self.hooks = hooks or RuntimeHooks()
        self.store = store
        self.approval_gate = approval_gate
        self.tool_gateway = tool_gateway
        self._audit_log: list[str] = []

    def plan(self, task: AgentTask) -> AgentTask:
        plan_task(task)
        task.status = AgentRunStatus.PLANNING
        self._audit("plan", task.task_id, f"planned {len(task.steps)} steps")
        return task

    def run(self, task: AgentTask) -> AgentRunResult:
        if not task.steps:
            task = self.plan(task)

        task.status = AgentRunStatus.RUNNING
        if self.store:
            self.store.save_task(task)

        started_at = time.time()
        step_results: list[StepResult] = []

        for step in task.steps:
            result = self.run_step(step, task_id=task.task_id)
            step_results.append(result)
            if not result.ok and not result.blocked:
                task.status = AgentRunStatus.FAILED
                break

        if task.status != AgentRunStatus.FAILED:
            task.status = AgentRunStatus.COMPLETED

        self._audit("run_complete", task.task_id, f"status={task.status.value}")
        if self.store:
            self.store.save_task(task)

        result = AgentRunResult(
            task_id=task.task_id,
            status=task.status,
            steps=step_results,
            total_ms=(time.time() - started_at) * 1000,
            audit_refs=list(self._audit_log),
        )
        if self.store:
            self.store.save_result(result)
        return result

    def run_step(
        self,
        step: AgentStep,
        task_id: str = "",
        worker_id: str = "",
    ) -> StepResult:
        started_at = time.time()

        if self.approval_gate:
            approval_result = self.approval_gate.check_step(
                step,
                task_id=task_id,
                worker_id=worker_id,
            )
            if approval_result is not None:
                approval_result.duration_ms = (time.time() - started_at) * 1000
                self._audit("step_approval_blocked", step.step_id,
                           approval_result.blocked_reason)
                return approval_result

        policy_result = check_step_policy(step)
        if policy_result is not None:
            policy_result.duration_ms = (time.time() - started_at) * 1000
            self._audit("step_blocked", step.step_id, policy_result.blocked_reason)
            return policy_result

        if step.kind == StepKind.SUMMARIZE:
            result = self._handle_summarize(step)
        elif step.kind == StepKind.RETRIEVE_CONTEXT:
            result = self._handle_retrieve_context(step)
        elif step.kind == StepKind.RUN_TESTS:
            result = self._handle_run_tests(step, task_id, worker_id)
        elif step.kind == StepKind.REVIEW:
            result = self._handle_review(step)
        elif step.kind in (StepKind.SHELL_COMMAND, StepKind.HTTP_CALL):
            result = self._handle_dangerous(step, task_id, worker_id)
        else:
            result = StepResult(
                step_id=step.step_id,
                ok=True,
                output="noop",
                evidence=["step_kind_noop"],
            )

        result.duration_ms = (time.time() - started_at) * 1000
        self._audit("step_result", step.step_id, f"ok={result.ok}")
        return result

    def _handle_summarize(self, step: AgentStep) -> StepResult:
        return StepResult(
            step_id=step.step_id,
            ok=True,
            output=f"[dry-run] Would summarize: {redact(step.goal)}",
            evidence=["summarize_dry_run"],
        )

    def _handle_retrieve_context(self, step: AgentStep) -> StepResult:
        if self.hooks.on_retrieve_context is None:
            return StepResult(
                step_id=step.step_id,
                ok=True,
                output=f"[dry-run] Would retrieve context for: {redact(step.goal)}",
                evidence=["retrieve_context_dry_run"],
            )

        try:
            output = self.hooks.on_retrieve_context(step.goal)
        except Exception as exc:
            return StepResult(
                step_id=step.step_id,
                ok=False,
                error=redact(str(exc)[:200]),
                evidence=["retrieve_context_hook_error"],
            )
        return StepResult(
            step_id=step.step_id,
            ok=True,
            output=redact(str(output)),
            evidence=["retrieve_context_hook"],
        )

    def _handle_run_tests(
        self,
        step: AgentStep,
        task_id: str = "",
        worker_id: str = "",
    ) -> StepResult:
        if self.tool_gateway:
            return self.tool_gateway.execute(step, task_id, worker_id)
        proposed_command = step.command or "pytest"
        if not self.dry_run:
            return self._blocked(step, "run_tests execution requires explicit shell gate")
        return StepResult(
            step_id=step.step_id,
            ok=True,
            output=f"[dry-run] Would run: {redact(proposed_command)}",
            evidence=["run_tests_dry_run"],
        )

    def _handle_review(self, step: AgentStep) -> StepResult:
        checklist = [
            "Check: code compiles without errors",
            "Check: tests pass",
            "Check: no hardcoded secrets",
            "Check: new code has tests",
            "Check: no permission expansion",
        ]
        return StepResult(
            step_id=step.step_id,
            ok=True,
            output="\n".join(checklist),
            evidence=["review_checklist"],
        )

    def _handle_dangerous(self, step: AgentStep, task_id: str = "",
                           worker_id: str = "") -> StepResult:
        """Route dangerous steps through tool gateway when connected."""
        if self.tool_gateway:
            return self.tool_gateway.execute(step, task_id, worker_id)
        return self._blocked(step, f"{step.kind.value} blocked by runtime")

    def _blocked(self, step: AgentStep, reason: str) -> StepResult:
        return StepResult(
            step_id=step.step_id,
            ok=False,
            blocked=True,
            blocked_reason=redact(reason),
            evidence=["runtime_blocked"],
        )

    def _audit(self, event: str, ref: str, detail: str = "") -> None:
        safe = f"{redact(event)}:{redact(ref)}"
        if detail:
            safe = f"{safe} ({redact(detail)})"
        self._audit_log.append(safe)
