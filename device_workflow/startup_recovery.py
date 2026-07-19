"""C1 Phase 3: startup recovery of in-flight workflow tasks from the ledger.

On server start, scan the execution-side task store for tasks that are not yet
terminal, replay each task's ledger events to warm the workflow projection, and
log any inconsistency between the task_store view and the ledger truth source.
"""

from __future__ import annotations

import logging
from typing import Any

from device_gateway.store import DeviceTaskStore
from device_workflow.orchestrator import WorkflowOrchestrator
from device_workflow.state import STATE_TO_STORE_STATUS, WorkflowTransitionError


def recover_inflight_tasks(
    task_store: DeviceTaskStore,
    workflow: WorkflowOrchestrator,
    logger: logging.Logger | None = None,
    limit: int = 1000,
) -> dict[str, Any]:
    """Replay ledger events for non-terminal tasks; log task_store/ledger mismatches.

    Runs synchronously; lifespan should execute it via ``asyncio.to_thread``.
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    task_ids = task_store.list_inflight_task_ids(limit=limit)
    recovered = 0
    missing_in_ledger = 0
    status_mismatch = 0

    for task_id in task_ids:
        try:
            workflow_state = workflow.get_state(task_id)
        except WorkflowTransitionError:
            logger.warning("startup recovery: task %s missing from ledger", task_id)
            missing_in_ledger += 1
            continue

        recovered += 1
        snapshot = task_store.task_snapshot(task_id)
        store_status = snapshot.get("status") if snapshot else None
        allowed = STATE_TO_STORE_STATUS.get(workflow_state, frozenset())
        if store_status is not None and store_status not in allowed:
            logger.warning(
                "startup recovery: task %s status mismatch: task_store=%s workflow=%s",
                task_id,
                store_status,
                workflow_state.value,
            )
            status_mismatch += 1

    return {
        "scanned": len(task_ids),
        "recovered": recovered,
        "missing_in_ledger": missing_in_ledger,
        "status_mismatch": status_mismatch,
    }
