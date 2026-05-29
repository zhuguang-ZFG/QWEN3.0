"""Task dispatcher — assigns tasks to nodes based on capabilities and load."""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field

_log = logging.getLogger(__name__)


@dataclass
class FleetTask:
    task_id: str = ""
    task_type: str = ""   # shell, inference, workspace
    command: str = ""
    required_gpu: bool = False
    required_model: str = ""
    payload: dict = field(default_factory=dict)
    status: str = "pending"  # pending, assigned, running, completed, failed
    assigned_to: str = ""
    created_at: float = field(default_factory=time.time)
    result: str = ""
    error: str = ""


class TaskDispatcher:
    """Manages task queue and dispatches to best-matching node."""

    def __init__(self) -> None:
        self._tasks: dict[str, FleetTask] = {}
        self._queue: list[str] = []  # task_ids in priority order

    def submit(
        self,
        task_type: str = "shell",
        command: str = "",
        required_gpu: bool = False,
        required_model: str = "",
        payload: dict | None = None,
    ) -> FleetTask:
        task_id = f"fleet-{uuid.uuid4().hex[:10]}"
        task = FleetTask(
            task_id=task_id,
            task_type=task_type,
            command=command,
            required_gpu=required_gpu,
            required_model=required_model,
            payload=payload or {},
        )
        self._tasks[task_id] = task
        self._queue.append(task_id)
        _log.info("fleet: task submitted id=%s type=%s gpu=%s", task_id, task_type, required_gpu)
        return task

    def dispatch(self, registry) -> tuple[FleetTask, str] | None:
        """Find best task+node pair. Returns (task, node_id) or None."""
        from fleet.node_registry import NodeRegistry

        online_nodes = registry.get_online_nodes()
        if not online_nodes:
            return None

        for task_id in list(self._queue):
            task = self._tasks.get(task_id)
            if task is None or task.status != "pending":
                self._queue = [tid for tid in self._queue if tid != task_id]
                continue

            node = self._find_best_node(task, online_nodes)
            if node:
                task.status = "assigned"
                task.assigned_to = node.node_id
                self._queue.remove(task_id)
                _log.info("fleet: task %s assigned to node %s", task_id, node.node_id)
                return task, node.node_id

        return None

    def claim_task(self, task_id: str, node_id: str) -> FleetTask | None:
        task = self._tasks.get(task_id)
        if task and task.status == "assigned" and task.assigned_to == node_id:
            task.status = "running"
            return task
        return None

    def complete_task(self, task_id: str, result: str = "", error: str = "") -> bool:
        task = self._tasks.get(task_id)
        if task is None:
            return False
        task.status = "failed" if error else "completed"
        task.result = result
        task.error = error
        return True

    def get_task(self, task_id: str) -> FleetTask | None:
        return self._tasks.get(task_id)

    def get_pending_tasks(self) -> list[FleetTask]:
        return [self._tasks[tid] for tid in self._queue if tid in self._tasks]

    def get_task_for_node(self, node_id: str) -> FleetTask | None:
        """Get next pending task assigned to this node."""
        for task_id in self._queue:
            task = self._tasks.get(task_id)
            if task and task.status == "pending":
                return task
        return None

    def cleanup(self, max_age: float = 3600) -> int:
        """Remove completed/failed tasks older than max_age seconds."""
        now = time.time()
        to_remove = []
        for tid, task in self._tasks.items():
            if task.status in ("completed", "failed"):
                if now - task.created_at > max_age:
                    to_remove.append(tid)
        for tid in to_remove:
            del self._tasks[tid]
            self._queue = [q for q in self._queue if q != tid]
        return len(to_remove)

    def _find_best_node(self, task: FleetTask, nodes) -> object | None:
        """Find best matching node for a task."""
        for node in nodes:
            if node.status == "busy":
                continue
            if task.required_gpu and not node.capabilities.gpu:
                continue
            if task.required_model:
                if task.required_model not in node.capabilities.models:
                    continue
            if task.task_type == "shell" and not node.capabilities.shell:
                continue
            if task.task_type == "workspace" and not node.capabilities.workspace:
                continue
            return node
        return None

    def to_dict(self) -> dict:
        return {
            "queue_size": len(self._queue),
            "tasks": {tid: {
                "status": t.status,
                "assigned_to": t.assigned_to,
                "task_type": t.task_type,
            } for tid, t in self._tasks.items()},
        }


_dispatcher = TaskDispatcher()


def get_dispatcher() -> TaskDispatcher:
    return _dispatcher
