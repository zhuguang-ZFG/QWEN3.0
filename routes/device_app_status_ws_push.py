"""Status WS push helpers: progress + firmware transitions (M2)."""

from __future__ import annotations

from typing import Any

from fastapi import WebSocket

from device_gateway.tasks import task_snapshot
from device_logic.http import now


def public_status_payload(status: dict[str, Any]) -> dict[str, Any]:
    """Drop internal poll-loop fields from client-facing status_snapshot."""
    return {k: v for k, v in status.items() if not str(k).startswith("_")}


def _coerce_progress(raw: Any) -> int | None:
    """Accept int-like progress in 0..100; reject bool and out-of-range values."""
    if isinstance(raw, bool) or raw is None:
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    if value < 0 or value > 100:
        return None
    return value


def progress_for_task(task_id: str) -> int | None:
    """Latest progress percent from motion events on the task store, if any."""
    snapshot = task_snapshot(task_id)
    if not snapshot:
        return None
    events = snapshot.get("events") or []
    for event in reversed(list(events)):
        if not isinstance(event, dict) or "progress" not in event:
            continue
        coerced = _coerce_progress(event["progress"])
        if coerced is not None:
            return coerced
    return None


def enrich_status_for_ws(status: dict[str, Any]) -> dict[str, Any]:
    """Attach poll-only fields used to detect progress transitions."""
    out = dict(status)
    task_id = out.get("activeTaskId")
    out["_taskProgress"] = progress_for_task(str(task_id)) if task_id else None
    return out


async def send_task_progress(
    websocket: WebSocket,
    device_id: str,
    previous: dict[str, Any],
    current: dict[str, Any],
) -> None:
    """Push task_progress when active task progress percent changes."""
    task_id = current.get("activeTaskId")
    if not task_id:
        return
    cur_prog = current.get("_taskProgress")
    prev_prog = previous.get("_taskProgress")
    if cur_prog is None or cur_prog == prev_prog:
        return
    if previous.get("activeTaskId") != task_id and prev_prog is None and cur_prog == 0:
        return
    payload = {
        "deviceId": device_id,
        "taskId": task_id,
        "progress": int(cur_prog),
        "timestamp": now(),
    }
    await websocket.send_json({"event": "task_progress", "payload": payload})


async def send_firmware_update(
    websocket: WebSocket,
    device_id: str,
    previous: dict[str, Any],
    current: dict[str, Any],
) -> None:
    """Push firmware_update only when an already-known version string changes.

    Offline snapshots use firmwareVersion=None; reconnecting with the same
    fw_rev must not look like an OTA (review W1).
    """
    prev_fw = previous.get("firmwareVersion")
    cur_fw = current.get("firmwareVersion")
    if prev_fw is None or not cur_fw or cur_fw == prev_fw:
        return
    payload = {
        "deviceId": device_id,
        "firmwareVersion": cur_fw,
        "previousFirmwareVersion": prev_fw,
        "timestamp": now(),
    }
    await websocket.send_json({"event": "firmware_update", "payload": payload})
