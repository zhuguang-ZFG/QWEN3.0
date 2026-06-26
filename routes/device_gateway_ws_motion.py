"""Motion-event handler for device gateway WebSocket uplink."""

from __future__ import annotations

import logging
from typing import Any

from device_gateway.protocol import ack_frame
from device_gateway.sessions import registry
from device_gateway.task_events import (
    process_motion_event_core,
    record_motion_event_side_effects,
)
from device_gateway.tasks import execute_recovery
from routes.ws_task_helpers import record_outcome_ledger, send_recovery_ack

_log = logging.getLogger(__name__)


async def _handle_motion_recovery(device_id: str, message: dict[str, Any], request_id: str | None) -> None:
    recovery_result = execute_recovery(message.get("task_id", ""), device_id, message)
    if not recovery_result:
        return
    _log.info(
        "device recovery action=%s attempt=%s device_id=%s task_id=%s",
        recovery_result["action"],
        recovery_result.get("attempt", 0),
        device_id,
        message.get("task_id", ""),
    )
    session = registry.get(device_id)
    if session is not None:
        await send_recovery_ack(session, device_id, message, request_id, recovery_result)


def _log_motion_phase(device_id: str, message: dict[str, Any]) -> None:
    phase = message.get("phase", "")
    task_id = str(message.get("task_id", ""))
    if phase in ("accepted", "running", "done", "failed"):
        _log.info("device task phase device_id=%s task_id=%s phase=%s", device_id, task_id, phase)


async def handle_motion_event(device_id: str, message: dict[str, Any], request_id: str | None) -> None:
    summary = process_motion_event_core(device_id, message)

    await _handle_motion_recovery(device_id, message, request_id)

    session = registry.get(device_id)
    if session is not None:
        session.mark_task_acknowledged(message["task_id"])
        await session.send_json(ack_frame("motion_event_ack", device_id, **summary, request_id=request_id))

    record_motion_event_side_effects(device_id, message)
    _log_motion_phase(device_id, message)

    phase = message.get("phase", "")
    if phase in ("done", "failed", "cancelled"):
        record_outcome_ledger(device_id, message, phase)
