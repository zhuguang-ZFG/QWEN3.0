"""Worker governor for agent run queue."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from agent_runtime.orchestrator_io import _emit
from agent_runtime.orchestrator_models import AgentRunLease, QueueStatus
from agent_runtime.orchestrator_queue import AgentRunQueue

_log = logging.getLogger(__name__)


@dataclass
class WorkerRecord:
    worker_id: str
    registered_at: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)
    status: str = "idle"
    active_lease_id: str = ""


class WorkerGovernor:
    """Worker lifecycle management wired to the task queue."""

    def __init__(self, queue: AgentRunQueue, heartbeat_timeout: float = 300.0) -> None:
        self.queue = queue
        self.heartbeat_timeout = heartbeat_timeout
        self._workers: dict[str, WorkerRecord] = {}

    def register(self, worker_id: str) -> WorkerRecord:
        existing = self._workers.get(worker_id)
        if existing:
            if existing.status != "quarantined":
                existing.last_heartbeat = time.time()
                if existing.status == "offline":
                    existing.status = "idle"
            return existing

        worker = WorkerRecord(worker_id=worker_id)
        self._workers[worker_id] = worker
        _emit("worker_registered", {"worker_id": worker_id})
        return worker

    def heartbeat(self, worker_id: str) -> WorkerRecord | None:
        worker = self._workers.get(worker_id)
        if not worker:
            return None
        if worker.status == "quarantined":
            return worker
        worker.last_heartbeat = time.time()
        if worker.status == "offline":
            worker.status = "idle"
        return worker

    def claim_for_worker(
        self, worker_id: str, request_id: str, lease_sec: float = 300.0
    ) -> AgentRunLease | None:
        worker = self._workers.get(worker_id)
        if not worker or worker.status in ("quarantined", "offline"):
            return None
        if worker.status == "busy" and worker.active_lease_id:
            return None
        if time.time() - worker.last_heartbeat > self.heartbeat_timeout:
            worker.status = "offline"
            self._release(worker)
            return None
        lease = self.queue.claim(request_id, worker_id, lease_sec=lease_sec)
        if lease:
            worker.status = "busy"
            worker.active_lease_id = request_id
        return lease

    def release_worker(self, worker_id: str) -> bool:
        worker = self._workers.get(worker_id)
        if not worker:
            return False
        self._release(worker)
        return True

    def quarantine(self, worker_id: str) -> bool:
        worker = self._workers.get(worker_id)
        if not worker:
            return False
        worker.status = "quarantined"
        self._release(worker)
        _emit("worker_quarantined", {"worker_id": worker_id})
        return True

    def mark_idle(self, worker_id: str) -> bool:
        worker = self._workers.get(worker_id)
        if not worker:
            return False
        if worker.status in ("quarantined", "offline"):
            return False
        worker.status = "idle"
        worker.active_lease_id = ""
        return True

    def mark_stale_offline(self) -> int:
        count = 0
        now = time.time()
        for worker in self._workers.values():
            if worker.status in ("idle", "busy") and (
                now - worker.last_heartbeat > self.heartbeat_timeout
            ):
                worker.status = "offline"
                self._release(worker)
                count += 1
        return count

    def get(self, worker_id: str) -> WorkerRecord | None:
        return self._workers.get(worker_id)

    def stats(self) -> dict:
        counts: dict[str, int] = {}
        for worker in self._workers.values():
            counts[worker.status] = counts.get(worker.status, 0) + 1
        return {
            "total": len(self._workers),
            "by_status": dict(sorted(counts.items())),
            "heartbeat_timeout": self.heartbeat_timeout,
        }

    def _release(self, worker: WorkerRecord) -> None:
        if worker.active_lease_id:
            self.queue._leases.pop(worker.active_lease_id, None)
            req = self.queue._requests.get(worker.active_lease_id)
            if req and req.status == QueueStatus.CLAIMED:
                req.status = QueueStatus.PENDING
            worker.active_lease_id = ""
        if worker.status not in ("quarantined", "offline"):
            worker.status = "idle"


def pre_plan_context(goal: str, limit: int = 3) -> str:
    """Query Outcome Ledger for relevant past outcomes before agent planning.

    Returns a concise context string with matching routing lessons
    (successful backends, failure patterns) that the agent can use
    to make better decisions. Returns empty string if nothing found.
    """
    if not goal or len(goal) < 5:
        return ""
    try:
        from session_memory.outcome_ledger import query as ledger_query

        events = ledger_query(limit=50)
        if not events:
            return ""

        q_lower = goal.lower()
        keywords = []
        for kw in ["code", "debug", "refactor", "test", "deploy", "api", "fix",
                    "build", "lint", "review", "push", "commit", "migrate"]:
            if kw in q_lower:
                keywords.append(kw)

        lessons: list[tuple[float, str]] = []
        for e in events:
            summary = (e.get("summary", "") or "").lower()
            score = 0.0
            for kw in keywords:
                if kw in summary:
                    score += 0.3
            if e.get("outcome") == "success":
                score += 0.15
            elif e.get("outcome") == "failed":
                score += 0.1  # still relevant — what to avoid
            backend = e.get("backend", "")
            if backend and backend.lower() in q_lower:
                score += 0.4
            if score > 0.25:
                lessons.append((score,
                    f"[{e.get('backend','?')}] {e.get('outcome','?')}: {e.get('summary','')[:120]}"))

        if not lessons:
            return ""

        lessons.sort(key=lambda x: -x[0])
        top = lessons[:limit]
        return "Relevant past outcomes:\n" + "\n".join(f"  {t}" for _, t in top)
    except ImportError:
        _log.debug("Outcome Ledger not available for agent planning")
    except Exception:
        _log.debug("pre_plan_context failed", exc_info=True)
    return ""
