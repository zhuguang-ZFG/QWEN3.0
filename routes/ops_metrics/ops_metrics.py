"""Operator telemetry endpoint — unified view across request, task, and device.

Provides authenticated endpoints:
- `/v1/ops/metrics` — snapshot across all subsystems
- `/v1/ops/correlate?id=X` — cross-system trace by request/task/device id
- `/v1/ops/correlate/summary` — recent correlation overview

All raw prompts, keys, paths, and device tokens are redacted.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from access_guard import require_private_api_key
from routes.ops_metrics import backend_ops, eval_ops, prometheus, summary
from routes.ops_metrics.collectors import ops_metrics_snapshot
from routes.ops_metrics.correlator import build_trace, correlation_summary

router = APIRouter(prefix="/v1/ops")
router.include_router(backend_ops.router)
router.include_router(eval_ops.router)
router.include_router(prometheus.router)


@router.get("/metrics", dependencies=[Depends(require_private_api_key)])
async def ops_metrics(request: Request) -> JSONResponse:
    return JSONResponse(ops_metrics_snapshot(request))


@router.get("/summary", dependencies=[Depends(require_private_api_key)])
async def ops_summary(request: Request) -> JSONResponse:
    return JSONResponse(summary.ops_summary_from_metrics(ops_metrics_snapshot(request)))


@router.get("/correlate/summary", dependencies=[Depends(require_private_api_key)])
async def ops_correlate_summary() -> JSONResponse:
    return JSONResponse(correlation_summary())


@router.get("/correlate", dependencies=[Depends(require_private_api_key)])
async def ops_correlate(
    id: str = Query(default=""),
    request_id: str = Query(default=""),
    task_id: str = Query(default=""),
    device_id: str = Query(default=""),
) -> JSONResponse:
    target = id or request_id or task_id or device_id
    if not target:
        return JSONResponse(
            {"error": "Provide one of: request_id, task_id, or device_id"},
            status_code=400,
        )
    return JSONResponse(build_trace(target))
