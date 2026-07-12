"""Task‑creation helpers extracted from device_app_tasks for size compliance."""

from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse

from device_gateway.path_validator import validate_capability_params
from device_gateway.task_creation import project_to_motion_task_async
from device_gateway.task_events import record_task_paused, record_task_resumed
from device_workflow.state import TaskState
from device_logic.gateway import dispatch_or_enqueue
from device_logic.http import err, str_field
from routes.device_app_task_store import insert_task_row
from routes.device_app_task_payloads import task_row_payload

APP_TASK_CAPABILITIES = frozenset(
    {
        "run_path",
        "write_text",
        "draw_generated",
        "draw_image",
        "handwriting",
        "home",
        "pause",
        "resume",
        "stop",
        "estop",
        "get_device_info",
    }
)
APP_TASK_SOURCES = frozenset({"api", "client", "voice", "scheduled"})


def _normalize_capability(capability: str, params: dict[str, Any]) -> tuple[str, dict[str, Any], str | None]:
    source_capability = capability
    capability = "draw_generated" if capability == "draw_image" else capability
    if capability not in APP_TASK_CAPABILITIES:
        return "", {}, f"unsupported capability: {source_capability}"
    task_params = dict(params)
    task_params.setdefault("source_capability", source_capability)
    if capability == "draw_generated" and "imageUrl" in task_params and "prompt" not in task_params:
        task_params["prompt"] = str(task_params["imageUrl"])
    return capability, task_params, None


async def _build_app_gateway_task(
    device_id: str,
    capability: str,
    params: dict[str, Any],
    source: str,
    request_id: str,
    account_id: str = "",
) -> tuple[dict[str, Any] | None, JSONResponse | None]:
    capability, task_params, error = _normalize_capability(capability, params)
    if error:
        return None, err(4001, error, 400)
    if account_id:
        task_params["_account_id"] = account_id
    sanitized, validation_error = validate_capability_params(capability, task_params)
    if validation_error:
        return None, err(4002, f"validation failed: {validation_error}", 400)
    # path_validator strips underscore keys; re-inject JWT account for gallery ownership.
    if account_id:
        sanitized["_account_id"] = account_id
    task = await project_to_motion_task_async(
        device_id,
        {"capability": capability, "params": sanitized, "source": source, "entrypoint": "app_api"},
        request_id or None,
    )
    task_error = task.get("error")
    if isinstance(task_error, dict):
        reason = task_error.get("reason") or task_error.get("code") or "task build failed"
        return None, err(4003, str(reason), 400)
    task["app_capability"] = capability
    return task, None


async def _dispatch_or_wait(
    device_id: str, task: dict[str, Any], source: str, params: dict[str, Any]
) -> tuple[dict[str, Any], str]:
    approval_required = source == "voice" and bool(params.get("requireApproval"))
    waiting = task.get("workflow_state") == TaskState.WAITING_APPROVAL.value or approval_required
    if waiting:
        return {"sent": False, "queueDepth": 0, "dispatchStatus": "waiting_approval"}, "pending"
    return await dispatch_or_enqueue(device_id, task), "approved"


async def _create_structured_task(
    device_id: str, account: dict[str, Any], body: dict[str, Any]
) -> dict[str, Any] | JSONResponse:
    source = str_field(body, "source") or "api"
    if source not in APP_TASK_SOURCES:
        return err(400, "invalid source", 400)
    raw_params = body.get("params")
    params: dict[str, Any] = dict(raw_params) if isinstance(raw_params, dict) else {}
    capability = str_field(body, "capability", "intent") or "write_text"
    task, error = await _build_app_gateway_task(
        device_id,
        capability,
        params,
        source,
        str_field(body, "requestId", "request_id"),
        account_id=str(account.get("id", "")),
    )
    if error:
        return error
    assert task is not None
    if capability == "pause":
        record_task_paused(str(task["task_id"]), device_id)
    elif capability == "resume":
        record_task_resumed(str(task["task_id"]), device_id)
    dispatch, status = await _dispatch_or_wait(device_id, task, source, params)
    row = insert_task_row(device_id, account, task, source, status, body, params)
    data = task_row_payload(row)
    data.update(dispatch)
    data.update({"task": task, "taskId": task["task_id"]})
    return data
