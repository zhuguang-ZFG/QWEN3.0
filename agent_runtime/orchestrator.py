"""Local queue with lease-based claiming for agent tasks.

The orchestrator provides submit/list/claim/finish/retry lifecycle operations
on top of the M18 store. It remains local and dry-run-first: execution still
flows through AgentRuntime, which defaults to no shell, no network, and no
workspace writes.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from agent_runtime.contract import (
    AgentRunResult,
    AgentRunStatus,
    AgentTask,
    redact_value,
)
from agent_runtime.executor import AgentRuntime
from agent_runtime.store import AgentRunStore, InMemoryAgentRunStore


_LOCAL_RUNNER_ID = "local-runner"


class QueueStatus(str, Enum):
    PENDING = "pending"
    CLAIMED = "claimed"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


@dataclass
class AgentRunRequest:
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    task: AgentTask | None = None
    task_id: str = ""
    goal: str = ""
    priority: int = 0
    created_at: float = field(default_factory=time.time)
    status: QueueStatus = QueueStatus.PENDING

    def __post_init__(self) -> None:
        if self.task:
            self.task_id = self.task.task_id
            self.goal = self.task.goal


@dataclass
class AgentRunLease:
    request_id: str
    worker_id: str
    claimed_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    lease_sec: float = 300.0

    def __post_init__(self) -> None:
        if self.expires_at <= 0:
            self.expires_at = self.claimed_at + self.lease_sec

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class AgentRunQueue:
    """Local in-memory task queue with lease-based claiming."""

    def __init__(
        self,
        store: AgentRunStore | None = None,
        runtime: AgentRuntime | None = None,
    ) -> None:
        self._requests: dict[str, AgentRunRequest] = {}
        self._leases: dict[str, AgentRunLease] = {}
        self.store = store or InMemoryAgentRunStore()
        self.runtime = runtime or AgentRuntime(store=self.store)

    def submit(self, task: AgentTask) -> AgentRunRequest:
        req = AgentRunRequest(task=task)
        req.status = QueueStatus.PENDING
        self._requests[req.request_id] = req
        self.store.save_task(task)
        _emit("task_submitted", {"request_id": req.request_id, "task_id": req.task_id})
        return req

    def list_requests(self, status: str = "", limit: int = 50) -> list[AgentRunRequest]:
        results = list(self._requests.values())
        if status:
            results = [req for req in results if req.status.value == status]
        results.sort(key=lambda req: (-req.priority, req.created_at))
        return results[:limit]

    def list_pending(self, limit: int = 50) -> list[AgentRunRequest]:
        return self.list_requests(status=QueueStatus.PENDING.value, limit=limit)

    def claim(
        self,
        request_id: str,
        worker_id: str,
        lease_sec: float = 300.0,
    ) -> AgentRunLease | None:
        req = self._requests.get(request_id)
        if not req:
            return None

        existing = self._leases.get(request_id)
        if existing and not existing.is_expired:
            return None
        if existing and existing.is_expired:
            self._leases.pop(request_id, None)
            if req.status == QueueStatus.CLAIMED:
                req.status = QueueStatus.PENDING

        if req.status != QueueStatus.PENDING:
            return None

        lease = AgentRunLease(
            request_id=request_id,
            worker_id=worker_id,
            lease_sec=lease_sec,
        )
        self._leases[request_id] = lease
        req.status = QueueStatus.CLAIMED
        _emit("task_claimed", {"request_id": request_id, "worker_id": worker_id})
        return lease

    def finish(self, request_id: str, result: AgentRunResult) -> bool:
        req = self._requests.get(request_id)
        if not req or result.task_id != req.task_id:
            return False
        if req.status in (
            QueueStatus.COMPLETED,
            QueueStatus.FAILED,
            QueueStatus.BLOCKED,
            QueueStatus.CANCELLED,
        ):
            return False

        req.status = _queue_status_for_result(result)
        if req.task:
            req.task.status = _task_status_for_queue(req.status)
            self.store.save_task(req.task)
        self.store.save_result(result)

        self._leases.pop(request_id, None)
        _emit("task_finished", {
            "request_id": request_id,
            "status": req.status.value,
        })
        return True

    def retry(self, request_id: str) -> AgentRunRequest | None:
        req = self._requests.get(request_id)
        if not req:
            return None
        if req.status not in (QueueStatus.FAILED, QueueStatus.BLOCKED):
            return None

        req.status = QueueStatus.PENDING
        if req.task:
            req.task.status = AgentRunStatus.PENDING
            self.store.save_task(req.task)
        self._leases.pop(request_id, None)
        _emit("task_retry", {"request_id": request_id})
        return req

    def run_one(self, request_id: str) -> AgentRunResult | None:
        req = self._requests.get(request_id)
        if not req or not req.task:
            return None
        if req.status == QueueStatus.PENDING:
            if self.claim(request_id, _LOCAL_RUNNER_ID) is None:
                return None
        elif req.status != QueueStatus.CLAIMED:
            return None

        lease = self._leases.get(request_id)
        if req.status == QueueStatus.CLAIMED and lease and lease.is_expired:
            req.status = QueueStatus.PENDING
            self._leases.pop(request_id, None)
            return None

        req.status = QueueStatus.RUNNING
        result = self.runtime.run(req.task)
        self.finish(request_id, result)
        return result

    def expire_leases(self) -> int:
        count = 0
        for request_id, lease in list(self._leases.items()):
            if not lease.is_expired:
                continue
            req = self._requests.get(request_id)
            if req and req.status == QueueStatus.CLAIMED:
                req.status = QueueStatus.PENDING
            self._leases.pop(request_id, None)
            count += 1
        return count

    def stats(self) -> dict[str, object]:
        counts: dict[str, int] = {}
        for req in self._requests.values():
            status = req.status.value
            counts[status] = counts.get(status, 0) + 1
        return {
            "total": len(self._requests),
            "active_leases": len(self._leases),
            "by_status": dict(sorted(counts.items())),
        }

    def recover_from_store(self) -> int:
        """Load unfinished tasks from store that are not already queued."""
        known_task_ids = {req.task_id for req in self._requests.values()}
        count = 0
        for task in self.store.list_tasks(limit=10000):
            if task.task_id in known_task_ids:
                continue
            if _has_terminal_or_blocked_result(self.store, task.task_id):
                continue
            if task.status in (
                AgentRunStatus.COMPLETED,
                AgentRunStatus.FAILED,
                AgentRunStatus.WAITING_APPROVAL,
                AgentRunStatus.CANCELLED,
            ):
                continue
            req = AgentRunRequest(task=task)
            req.status = QueueStatus.PENDING
            self._requests[req.request_id] = req
            known_task_ids.add(task.task_id)
            count += 1
        return count


def _queue_status_for_result(result: AgentRunResult) -> QueueStatus:
    if any(step.blocked for step in result.steps):
        return QueueStatus.BLOCKED
    if result.ok:
        return QueueStatus.COMPLETED
    return QueueStatus.FAILED


def _task_status_for_queue(status: QueueStatus) -> AgentRunStatus:
    if status == QueueStatus.COMPLETED:
        return AgentRunStatus.COMPLETED
    if status == QueueStatus.FAILED:
        return AgentRunStatus.FAILED
    if status == QueueStatus.BLOCKED:
        return AgentRunStatus.WAITING_APPROVAL
    if status == QueueStatus.CANCELLED:
        return AgentRunStatus.CANCELLED
    if status == QueueStatus.RUNNING:
        return AgentRunStatus.RUNNING
    return AgentRunStatus.PENDING


def _has_terminal_or_blocked_result(store: AgentRunStore, task_id: str) -> bool:
    result = store.get_result(task_id)
    if result is None:
        return False
    if any(step.blocked for step in result.steps):
        return True
    return result.status in (AgentRunStatus.COMPLETED, AgentRunStatus.FAILED)


def _emit(event: str, data: dict[str, Any]) -> None:
    try:
        safe_data = redact_value(data)
        from agent_runtime.events import _safe_emit, _safe_stream

        _safe_emit(f"orchestrator_{event}", safe_data)
        _safe_stream(event, safe_data)
    except Exception:
        pass
