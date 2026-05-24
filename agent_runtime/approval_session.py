"""Operator approval session with a reviewable evidence bundle."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from agent_runtime.approval import ApprovalGate, ApprovalRequest
from agent_runtime.audit_trail import audit_event
from agent_runtime.contract import redact


@dataclass
class ApprovalSession:
    approval_id: str
    task_id: str = ""
    worker_id: str = ""
    kind: str = ""
    goal: str = ""
    command: str = ""
    status: str = "pending"
    created_at: float = field(default_factory=time.time)
    decided_at: float = 0.0
    decided_by: str = ""
    evidence: list[str] = field(default_factory=list)
    audit_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "approval_id": redact(self.approval_id),
            "task_id": redact(self.task_id),
            "worker_id": redact(self.worker_id),
            "kind": self.kind,
            "goal": redact(self.goal),
            "command": redact(self.command),
            "status": self.status,
            "created_at": self.created_at,
            "decided_at": self.decided_at,
            "decided_by": redact(self.decided_by),
            "evidence": [redact(item) for item in self.evidence],
            "audit_refs": [redact(item) for item in self.audit_refs],
        }


def open_session(
    req: ApprovalRequest,
    evidence: list[str] | None = None,
) -> ApprovalSession:
    return ApprovalSession(
        approval_id=req.approval_id,
        task_id=req.task_id,
        worker_id=req.worker_id,
        kind=req.kind.value,
        goal=req.goal,
        command=req.command,
        status=req.status.value,
        created_at=req.created_at,
        evidence=list(evidence or []),
    )


def approve_session(
    gate: ApprovalGate,
    session: ApprovalSession,
    operator: str = "operator",
) -> ApprovalSession:
    ok = gate.approve(session.approval_id)
    if ok:
        session.status = "approved"
        session.decided_at = time.time()
        session.decided_by = redact(operator)
        ref = _safe_audit("operator_approve", session)
        if ref:
            session.audit_refs.append(ref)
    return session


def deny_session(
    gate: ApprovalGate,
    session: ApprovalSession,
    reason: str = "",
    operator: str = "operator",
) -> ApprovalSession:
    ok = gate.deny(session.approval_id)
    if ok:
        session.status = "denied"
        session.decided_at = time.time()
        session.decided_by = redact(operator)
        if reason:
            session.evidence.append(f"deny_reason: {redact(reason)}")
        ref = _safe_audit("operator_deny", session)
        if ref:
            session.audit_refs.append(ref)
    return session


def format_session(session: ApprovalSession) -> str:
    lines = [
        f"Approval Session: {redact(session.approval_id)}",
        f"  Task: {redact(session.task_id)}  Worker: {redact(session.worker_id)}",
        f"  Kind: {session.kind}  Status: {session.status}",
        f"  Goal: {redact(session.goal[:100])}",
    ]
    if session.command:
        lines.append(f"  Command: {redact(session.command[:200])}")
    if session.evidence:
        safe_evidence = ", ".join(redact(item) for item in session.evidence[:5])
        lines.append(f"  Evidence: {safe_evidence}")
    if session.decided_by:
        lines.append(f"  Decided by: {redact(session.decided_by)} at {session.decided_at:.0f}")
    return "\n".join(lines)


def _safe_audit(event: str, session: ApprovalSession) -> str:
    try:
        ref = audit_event(
            event,
            task_id=session.task_id,
            approval_id=session.approval_id,
        )
        return ref.audit_id
    except Exception:
        return ""
