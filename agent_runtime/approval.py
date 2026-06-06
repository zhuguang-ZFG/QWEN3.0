"""Approval gate for real tool execution requests.

The gate does not execute tools. In dry-run mode it blocks dangerous step
kinds directly. In non-dry-run mode it creates approval requests for steps that
would require real authority and only allows an exact approved request.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum

_log = logging.getLogger(__name__)

from agent_runtime.contract import AgentStep, StepKind, StepResult, redact


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


DANGEROUS_KINDS = frozenset({
    StepKind.SHELL_COMMAND,
    StepKind.HTTP_CALL,
})

REQUIRES_APPROVAL_KINDS = frozenset({
    StepKind.SHELL_COMMAND,
    StepKind.HTTP_CALL,
    StepKind.RUN_TESTS,
})


@dataclass
class ApprovalRequest:
    approval_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    step_id: str = ""
    task_id: str = ""
    worker_id: str = ""
    kind: StepKind = StepKind.NOOP
    goal: str = ""
    command: str = ""
    reason: str = ""
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    ttl_sec: float = 600.0

    def __post_init__(self) -> None:
        if self.expires_at <= 0:
            self.expires_at = self.created_at + self.ttl_sec

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    def matches(self, step: AgentStep, task_id: str = "", worker_id: str = "") -> bool:
        return (
            self.step_id == step.step_id
            and self.task_id == task_id
            and self.worker_id == worker_id
            and self.kind == step.kind
            and self.command == step.command
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "approval_id": redact(self.approval_id),
            "step_id": redact(self.step_id),
            "task_id": redact(self.task_id),
            "worker_id": redact(self.worker_id),
            "kind": self.kind.value,
            "goal": redact(self.goal),
            "command": redact(self.command),
            "reason": redact(self.reason),
            "status": self.status.value,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
        }


class ApprovalGate:
    """Intercept steps and track explicit approval decisions."""

    def __init__(self, dry_run: bool = True) -> None:
        self.dry_run = dry_run
        self._requests: dict[str, ApprovalRequest] = {}
        self._audit_log: list[str] = []

    def check_step(
        self,
        step: AgentStep,
        task_id: str = "",
        worker_id: str = "",
    ) -> StepResult | None:
        if self.dry_run:
            if step.kind in DANGEROUS_KINDS:
                return StepResult(
                    step_id=step.step_id,
                    ok=False,
                    blocked=True,
                    blocked_reason=f"dry_run: {step.kind.value} blocked",
                )
            return None

        existing = self._find_matching(step, task_id, worker_id)
        if existing:
            if existing.status == ApprovalStatus.APPROVED and not existing.is_expired:
                return None
            if existing.status in (
                ApprovalStatus.PENDING,
                ApprovalStatus.APPROVED,
            ) and existing.is_expired:
                existing.status = ApprovalStatus.EXPIRED
            return StepResult(
                step_id=step.step_id,
                ok=False,
                blocked=True,
                blocked_reason=(
                    f"approval required: {existing.approval_id} "
                    f"(status={existing.status.value})"
                ),
            )

        if step.kind in REQUIRES_APPROVAL_KINDS:
            req = self.request_approval(step, task_id, worker_id)
            return StepResult(
                step_id=step.step_id,
                ok=False,
                blocked=True,
                blocked_reason=(
                    f"approval required: {req.approval_id} "
                    f"(status={req.status.value})"
                ),
            )

        return None

    def request_approval(
        self,
        step: AgentStep,
        task_id: str = "",
        worker_id: str = "",
    ) -> ApprovalRequest:
        existing = self._find_matching(step, task_id, worker_id)
        if existing:
            if existing.status == ApprovalStatus.PENDING and existing.is_expired:
                existing.status = ApprovalStatus.EXPIRED
            return existing

        req = ApprovalRequest(
            step_id=step.step_id,
            task_id=task_id,
            worker_id=worker_id,
            kind=step.kind,
            goal=step.goal,
            command=step.command,
            reason=f"Step '{step.step_id}' ({step.kind.value}) requires approval",
        )
        self._requests[req.approval_id] = req
        self._audit(f"approval_requested:{req.approval_id}:{step.kind.value}")
        return req

    def approve(self, approval_id: str) -> bool:
        req = self._requests.get(approval_id)
        if not req or req.is_expired:
            if req and req.status == ApprovalStatus.PENDING:
                req.status = ApprovalStatus.EXPIRED
            return False
        if req.status != ApprovalStatus.PENDING:
            return False
        req.status = ApprovalStatus.APPROVED
        self._audit(f"approval_granted:{approval_id}")
        return True

    def deny(self, approval_id: str) -> bool:
        req = self._requests.get(approval_id)
        if not req:
            return False
        if req.status != ApprovalStatus.PENDING:
            return False
        req.status = ApprovalStatus.DENIED
        self._audit(f"approval_denied:{approval_id}")
        return True

    def expire_stale(self) -> int:
        count = 0
        for req in list(self._requests.values()):
            if req.status == ApprovalStatus.PENDING and req.is_expired:
                req.status = ApprovalStatus.EXPIRED
                count += 1
        return count

    def get_pending(self) -> list[ApprovalRequest]:
        return [
            request
            for request in self._requests.values()
            if request.status == ApprovalStatus.PENDING and not request.is_expired
        ]

    def get_request(self, approval_id: str) -> ApprovalRequest | None:
        return self._requests.get(approval_id)

    def stats(self) -> dict[str, object]:
        counts: dict[str, int] = {}
        for request in self._requests.values():
            counts[request.status.value] = counts.get(request.status.value, 0) + 1
        return {
            "total": len(self._requests),
            "by_status": dict(sorted(counts.items())),
        }

    def _audit(self, msg: str) -> None:
        try:
            safe_msg = redact(msg)
        except Exception as exc:
            _log.warning("operation failed: %s", exc)
            safe_msg = "[REDACTED]"
        self._audit_log.append(safe_msg)
        try:
            from agent_runtime.events import _safe_emit

            _safe_emit("approval_event", {"message": safe_msg})
        except Exception as exc:
            _log.debug("approval event emit skipped: %s", type(exc).__name__)

    def _find_matching(
        self,
        step: AgentStep,
        task_id: str = "",
        worker_id: str = "",
    ) -> ApprovalRequest | None:
        for request in self._requests.values():
            if request.matches(step, task_id, worker_id):
                return request
        return None
