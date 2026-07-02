"""设备任务时间线路由 — 独立拆分以控制 device_gateway.py 行数。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from access_guard import require_private_api_key
from device_gateway.protocol import ProtocolError, error_frame
from device_gateway.task_timeline import build_device_timeline, build_task_timeline

router = APIRouter(prefix="/device/v1", tags=["device-timeline"])


@router.get("/tasks/{task_id}/timeline", dependencies=[Depends(require_private_api_key)])
async def device_task_timeline(task_id: str) -> JSONResponse:
    """查询单个任务的状态流转时间线。"""
    timeline = build_task_timeline(task_id)
    if not timeline:
        return JSONResponse(
            status_code=404,
            content=error_frame(ProtocolError("E_TASK_NOT_FOUND", f"Task {task_id} not found")),
        )
    return JSONResponse(timeline)


@router.get("/devices/{device_id}/timeline", dependencies=[Depends(require_private_api_key)])
async def device_task_history_timeline(
    device_id: str,
    limit: int = Query(50, ge=1, le=200),
) -> JSONResponse:
    """查询设备的任务历史时间线（聚合所有任务的状态流转）。"""
    timelines = build_device_timeline(device_id, limit=limit)
    return JSONResponse(
        {
            "device_id": device_id,
            "tasks": timelines,
            "count": len(timelines),
        }
    )
