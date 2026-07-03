"""LiMa device gateway read-only query routes.

Extracted from ``routes.device_gateway`` (R batch deep-slim) so the main
module owns writes (events, tasks, ws/ticket, ws) while this module owns
the three GET query endpoints: task status, task list, and device drawing
history. Shares the ``/device/v1`` prefix with the main router; FastAPI
merges same-prefix routers without conflict.

Runtime singletons (``task_store``, ``task_snapshot``, ``artifact_store``,
``artifacts_for_device``) are imported lazily inside each handler — mirroring
the original deferred-import style — so ``install_task_store_for_tests`` /
``set_task_store_for_tests`` swaps remain visible here. A top-level
``from ... import task_store`` would bind the pre-swap instance and break
test isolation (lesson learned R batch 2026-07-03).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from access_guard import require_private_api_key
from device_gateway.protocol import ProtocolError, error_frame

router = APIRouter(prefix="/device/v1")


@router.get("/tasks/{task_id}", dependencies=[Depends(require_private_api_key)])
async def device_task_status(task_id: str) -> JSONResponse:
    """查询任务状态"""
    from device_artifacts.store import artifact_store
    from device_gateway.tasks import task_snapshot

    snapshot = task_snapshot(task_id)
    if not snapshot:
        return JSONResponse(
            status_code=404,
            content=error_frame(ProtocolError("E_TASK_NOT_FOUND", f"Task {task_id} not found")),
        )

    terminal_phase = ""
    for event in reversed(snapshot.get("events", [])):
        phase = event.get("phase", "")
        if phase in {"done", "failed", "cancelled"}:
            terminal_phase = phase
            break
    terminal_result = None
    if terminal_phase:
        terminal_artifacts = artifact_store.artifacts_for_task(task_id, "terminal_result")
        if terminal_artifacts:
            terminal_result = terminal_artifacts[-1].to_dict()

    return JSONResponse(
        {
            "task_id": task_id,
            "status": snapshot.get("status", "unknown"),
            "terminal_phase": terminal_phase,
            "task": snapshot.get("task", {}),
            "events": snapshot.get("events", []),
            "terminal_result": terminal_result,
        }
    )


@router.get("/tasks", dependencies=[Depends(require_private_api_key)])
async def device_task_list(
    device_id: str = "",
    status: str = "",
    limit: int = Query(20, ge=1, le=100),
) -> JSONResponse:
    """查询任务列表"""
    from device_gateway.store import task_store

    if not device_id:
        return JSONResponse({"tasks": [], "count": 0})

    tasks = task_store.list_tasks_for_device(device_id, status=status, limit=limit)

    return JSONResponse(
        {
            "tasks": tasks,
            "count": len(tasks),
        }
    )


@router.get("/devices/{device_id}/history", dependencies=[Depends(require_private_api_key)])
async def device_drawing_history(
    device_id: str,
    artifact_type: str = "",
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> JSONResponse:
    """查询设备绘图历史"""
    from device_artifacts.store import artifacts_for_device

    artifacts = artifacts_for_device(
        device_id=device_id,
        artifact_type=artifact_type if artifact_type else None,
        limit=limit,
        offset=offset,
    )

    # 转换为可序列化的格式
    history = []
    for artifact in artifacts:
        history.append(
            {
                "task_id": artifact.task_id,
                "artifact_type": artifact.artifact_type,
                "content": artifact.content,
                "content_hash": artifact.content_hash,
                "created_at": artifact.created_at,
            }
        )

    return JSONResponse(
        {
            "device_id": device_id,
            "history": history,
            "count": len(history),
            "offset": offset,
            "limit": limit,
        }
    )
