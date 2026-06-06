"""Agent run queue with lease-based claiming."""

from __future__ import annotations

import logging
import os
import time
from typing import Any

_log = logging.getLogger(__name__)

from agent_runtime.contract import AgentRunResult, AgentRunStatus, AgentTask
from agent_runtime.executor import AgentRuntime
from agent_runtime.orchestrator_io import (
    _emit,
    _has_terminal_or_blocked_result,
    _json_dumps,
    _json_loads,
    _lease_record,
    _parse_queue_status,
    _queue_status_for_result,
    _request_record,
    _safe_float,
    _safe_int,
    _state_path,
    _task_status_for_queue,
)
from agent_runtime.orchestrator_models import (
    AgentRunLease,
    AgentRunRequest,
    QueueStatus,
)
from agent_runtime.store import AgentRunStore, InMemoryAgentRunStore

_LOCAL_RUNNER_ID = "local-runner"

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

    def save_state(self) -> bool:
        """Persist queue requests and leases as JSONL state records."""
        try:
            records = []
            for req in self._requests.values():
                records.append(_request_record(req))
            for lease in self._leases.values():
                records.append(_lease_record(lease))
            path = _state_path()
            state_dir = os.path.dirname(path)
            if state_dir:
                os.makedirs(state_dir, exist_ok=True)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                for rec in records:
                    f.write(_json_dumps(rec) + "\n")
            os.replace(tmp, path)
            return True
        except OSError:
            return False

    def load_state(self, store: AgentRunStore | None = None) -> int:
        """Load queue state from persisted JSONL. Returns count of restored requests."""
        path = _state_path()
        store = store or self.store
        loaded = 0
        if not os.path.exists(path):
            return self.recover_from_store()

        request_records: list[dict[str, Any]] = []
        lease_records: list[dict[str, Any]] = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                rec = _json_loads(line.strip())
                if not rec:
                    continue
                record_type = rec.get("_type", "")
                if record_type == "queue_request":
                    request_records.append(rec)
                elif record_type == "queue_lease":
                    lease_records.append(rec)

        for rec in request_records:
            if self._restore_request(rec, store):
                loaded += 1
        for rec in lease_records:
            self._restore_lease(rec)

        self._release_claims_without_leases()
        self.expire_leases()
        loaded += self.recover_from_store()
        return loaded

    def _restore_request(self, rec: dict, store: AgentRunStore) -> bool:
        rid = str(rec.get("request_id", ""))
        if not rid or rid in self._requests:
            return False
        task_id = str(rec.get("task_id", ""))
        task = store.get_task(task_id)
        safe_priority = _safe_int(rec.get("priority", 0))
        safe_created_at = _safe_float(rec.get("created_at", time.time()))
        req = AgentRunRequest(
            request_id=rid,
            task=task,
            task_id=task_id,
            goal=str(rec.get("goal", "")),
            priority=safe_priority,
            created_at=safe_created_at,
        )
        req.status = _parse_queue_status(rec.get("status", "pending"))
        self._requests[rid] = req
        return True

    def _restore_lease(self, rec: dict) -> None:
        rid = str(rec.get("request_id", ""))
        if not rid or rid in self._leases or rid not in self._requests:
            return
        lease = AgentRunLease(
            request_id=rid,
            worker_id=str(rec.get("worker_id", "unknown")),
            claimed_at=_safe_float(rec.get("claimed_at", 0)),
            expires_at=_safe_float(rec.get("expires_at", 0)),
            lease_sec=_safe_float(rec.get("lease_sec", 300)),
        )
        if not lease.is_expired:
            self._leases[rid] = lease
            if self._requests[rid].status == QueueStatus.PENDING:
                self._requests[rid].status = QueueStatus.CLAIMED

    def _release_claims_without_leases(self) -> None:
        for request_id, req in self._requests.items():
            if req.status == QueueStatus.CLAIMED and request_id not in self._leases:
                req.status = QueueStatus.PENDING

    def clear_state_file(self) -> None:
        """Remove the persisted state file. For test cleanup."""
        try:
            os.remove(_state_path())
        except OSError:
            _log.debug("orchestrator_queue: optional dependency or operation failed", exc_info=True)
    def save_and_snapshot(self) -> dict:
        """Save state and return a snapshot for debugging."""
        self.save_state()
        return self.stats()


