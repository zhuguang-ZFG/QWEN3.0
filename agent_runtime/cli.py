"""Operator CLI for human-readable console operations for agent runtime.

Answers: pending approvals, approve/deny, retry, quarantine, resume, stats.
All output is text or JSON, safe for terminal or programmatic use.
"""

from __future__ import annotations

import json
import time
from typing import Any

from agent_runtime.approval import ApprovalGate
from agent_runtime.contract import redact
from agent_runtime.orchestrator import AgentRunQueue, WorkerGovernor
from agent_runtime.store import AgentRunStore
from agent_runtime.audit_trail import audit_event


def list_pending_approvals(gate: ApprovalGate) -> str:
    pending = gate.get_pending()
    if not pending:
        return "No pending approvals."
    lines = ["Pending approvals:"]
    for req in pending:
        expires_in = max(0, req.expires_at - time.time())
        lines.append(f"  [{redact(req.approval_id)}] step={redact(req.step_id)} "
                     f"kind={req.kind.value} task={redact(req.task_id)} "
                     f"worker={redact(req.worker_id)} expires_in={expires_in:.0f}s")
    return "\n".join(lines)


def approve(gate: ApprovalGate, approval_id: str) -> str:
    ok = gate.approve(approval_id)
    audit_event("operator_approve", approval_id=approval_id)
    return f"Approved: {approval_id}" if ok else f"Failed to approve: {approval_id}"


def deny_approval(gate: ApprovalGate, approval_id: str) -> str:
    ok = gate.deny(approval_id)
    audit_event("operator_deny", approval_id=approval_id)
    return f"Denied: {approval_id}" if ok else f"Failed to deny: {approval_id}"


def retry_task(queue: AgentRunQueue, request_id: str) -> str:
    req = queue.retry(request_id)
    audit_event("operator_retry", request_id=request_id)
    if req:
        return f"Retrying: {request_id} (status={req.status.value})"
    return f"Cannot retry: {request_id}"


def quarantine_worker(gov: WorkerGovernor, worker_id: str) -> str:
    ok = gov.quarantine(worker_id)
    audit_event("operator_quarantine", worker_id=worker_id)
    return f"Quarantined: {worker_id}" if ok else f"Worker not found: {worker_id}"


def queue_summary(queue: AgentRunQueue) -> str:
    s = queue.stats()
    lines = [f"Queue: {s['total']} requests, {s['active_leases']} active leases"]
    by_status = s.get("by_status", {})
    if isinstance(by_status, dict):
        for status, count in by_status.items():
            lines.append(f"  {status}: {count}")
    return "\n".join(lines)


def worker_summary(gov: WorkerGovernor) -> str:
    s = gov.stats()
    lines = [f"Workers: {s['total']}"]
    by_status = s.get("by_status", {})
    if isinstance(by_status, dict):
        for status, count in by_status.items():
            lines.append(f"  {status}: {count}")
    return "\n".join(lines)


def status_snapshot(queue: AgentRunQueue, gov: WorkerGovernor | None = None,
                    gate: ApprovalGate | None = None,
                    store: AgentRunStore | None = None) -> str:
    lines = [queue_summary(queue)]
    if gov:
        lines.append(worker_summary(gov))
    if gate:
        lines.append(f"Approvals: {gate.stats()['total']} total")
        pending = gate.get_pending()
        if pending:
            lines.append(f"  Pending: {len(pending)}")
    if store:
        from agent_runtime.store import count_by_status
        counts = count_by_status(store)
        lines.append(f"Store tasks: {sum(counts.values())} total")
        for status, count in sorted(counts.items()):
            lines.append(f"  {status}: {count}")
    return "\n".join(lines)


def status_snapshot_json(queue: AgentRunQueue, gov: WorkerGovernor | None = None,
                          gate: ApprovalGate | None = None,
                          store: AgentRunStore | None = None) -> str:
    data: dict[str, Any] = {"queue": queue.stats()}
    if gov:
        data["workers"] = gov.stats()
    if gate:
        data["approvals"] = gate.stats()
    if store:
        from agent_runtime.store import count_by_status
        data["store"] = count_by_status(store)
    return json.dumps(data, indent=2, ensure_ascii=False)
