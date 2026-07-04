"""Helper functions for WebSocket task handlers (recovery acks, outcome ledger)."""

from __future__ import annotations

import logging
from typing import Any

from device_gateway.protocol import ack_frame
from device_gateway.sessions import DeviceSession
from device_gateway.tasks import (
    mark_task_dispatched,
    remove_pending_task,
)

_log = logging.getLogger(__name__)


async def send_recovery_ack(
    session: DeviceSession,
    device_id: str,
    message: dict[str, Any],
    request_id: str | None,
    recovery_result: dict[str, Any],
) -> None:
    action = recovery_result["action"]
    retry_task = recovery_result.get("task")
    if action == "home":
        await session.send_json(
            ack_frame(
                "home_command",
                device_id,
                task_id=message.get("task_id", ""),
                reason="recovery_action_home",
                request_id=request_id,
            )
        )
    elif action == "retry" and retry_task:
        await session.send_json(
            ack_frame(
                "motion_task_retry",
                device_id,
                task_id=message.get("task_id", ""),
                task=retry_task,
                attempt=recovery_result.get("attempt", 0),
                request_id=request_id,
            )
        )
        # Avoid double-delivery via pending queue; task is already inflight.
        session.mark_task_dispatched(retry_task)
        mark_task_dispatched(retry_task["task_id"])
        remove_pending_task(device_id, retry_task["task_id"])


def record_outcome_ledger(device_id: str, message: dict[str, Any], phase: str) -> None:
    # P4 瘦身：session_memory.outcome_ledger 已删除，outcome 记录退役
    _log.debug("outcome ledger (retired): device=%s phase=%s task=%s", device_id, phase, message.get("task_id", ""))
