"""dlc_api P1 routes: /dlc/tasks/* contract for device drawing/writing."""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse

from config.settings import DEVICE, REDIS
from device_gateway.delivery_status import QUEUED_NO_DELIVERY_STATUS, QUEUED_NO_DELIVERY_USER_MESSAGE
from dlc_api.deps import verify_dlc_api_token
from dlc_api.schemas import (
    DeviceStatusResponse,
    TaskDispatchRequest,
    TaskDispatchResponse,
    TaskPreviewRequest,
    TaskPreviewResponse,
    TaskValidateRequest,
    TaskValidateResponse,
)
from dlc_core import (
    dispatch_task,
    get_device_status,
    handle_draw,
    handle_draw_from_image,
    handle_write,
    validate_path,
)
from dlc_api.idempotency import IdempotencyUnavailableError
from dlc_api.idempotency import claim_idempotency_key as _claim_idempotency_key
from dlc_api.idempotency import release_idempotency_key as _release_idempotency_key
from dlc_api.motion_payload import build_dispatch_payload as _build_dispatch_payload
from device_gateway.image_url_validation import validate_image_url_async
from device_gateway.store import task_store_health
from routes.rate_limit_helper import check_key_limit

logger = logging.getLogger(__name__)
router = APIRouter()


def _preview_from_result(result: dict[str, Any]) -> TaskPreviewResponse:
    """Build a TaskPreviewResponse from a dlc_core result dict."""
    return TaskPreviewResponse(
        status=result["status"],
        path_data=result.get("path_data"),
        svg_path=result.get("svg_path"),
        preview_svg=result.get("preview_svg"),
        width=result.get("width"),
        height=result.get("height"),
        model=result.get("model"),
        error=result.get("error"),
    )


async def _validate_image_url(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    """DNS (getaddrinfo) is blocking — always run off the event loop (GW-WD)."""
    return await validate_image_url_async(str(payload.get("image_url", "")))


def _quota_for(task_type: str) -> int:
    """S3: per-minute quota for a task type. draw_from_image is CPU/cost heavy → lower."""
    if task_type == "draw_from_image":
        return DEVICE.dlc_image_per_min
    return DEVICE.dlc_task_per_min


@router.get("/health")
@router.get("/health/ready")
async def health():
    """Lightweight health endpoint for load balancers and smoke tests."""
    base = {"service": "dlc-drawing", "version": "0.4.0-p3"}
    try:
        backend = task_store_health().get("backend", "memory")
    except Exception:
        logger.warning("task_store_health 调用失败，按 memory 处理", exc_info=True)
        backend = "memory"
    deps: dict[str, str] = {"task_store": backend}

    # Honest probe: env expects Redis but store still memory → misconfigured.
    store_pref = os.environ.get("LIMA_DEVICE_TASK_STORE", "").strip().lower()
    env_wants_redis = store_pref == "redis" or bool(REDIS.device_redis_url)
    if env_wants_redis and backend != "redis":
        logger.warning(
            "env expects Redis (LIMA_DEVICE_TASK_STORE/LIMA_DEVICE_REDIS_URL) but backend is %s",
            backend,
        )
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", **base, "dependencies": deps},
        )

    if backend == "redis":
        try:
            from device_gateway.store import task_store

            task_store.ping()
        except Exception:
            logger.warning("Redis ping 失败", exc_info=True)
            return JSONResponse(
                status_code=503,
                content={"status": "degraded", **base, "dependencies": deps},
            )
    return {"status": "ok", **base, "dependencies": deps}


@router.get("/dlc/devices/{device_id}/status", response_model=DeviceStatusResponse)
async def get_device_status_endpoint(
    device_id: str,
    caller_device_id: str = Depends(verify_dlc_api_token),
) -> DeviceStatusResponse:
    """Return the canonical runtime status for one device."""
    if device_id != caller_device_id:
        raise HTTPException(status_code=403, detail="device_id mismatch")
    return DeviceStatusResponse(**(await get_device_status(device_id)))


@router.post("/dlc/tasks/preview", response_model=TaskPreviewResponse)
async def preview_task(
    body: TaskPreviewRequest,
    caller_device_id: str = Depends(verify_dlc_api_token),
) -> TaskPreviewResponse | JSONResponse:
    """Generate a motion path preview without dispatching to the device."""
    if body.device_id != caller_device_id:
        return TaskPreviewResponse(status="rejected", error="device_id mismatch")

    limited = check_key_limit(f"dlc_preview:{caller_device_id}", _quota_for(body.type))
    if limited is not None:
        return limited

    if body.type == "write_text":
        text = str(body.payload.get("text", "")).strip()
        if not text:
            return TaskPreviewResponse(status="failed", error="text is required")
        return _preview_from_result(await handle_write(text))

    if body.type == "draw_generated":
        prompt = str(body.payload.get("prompt", "")).strip()
        if not prompt:
            return TaskPreviewResponse(status="failed", error="prompt is required")
        result = await handle_draw(prompt, device_id=body.device_id, allow_dashscope=False)
        return _preview_from_result(result)

    if body.type == "draw_from_image":
        image_url, err = await _validate_image_url(body.payload)
        if err or image_url is None:
            return TaskPreviewResponse(status="failed", error=err or "image_url is required")
        result = await handle_draw_from_image(image_url, device_id=body.device_id)
        return _preview_from_result(result)

    return TaskPreviewResponse(status="failed", error="unsupported type")


@router.post("/dlc/tasks/dispatch", response_model=TaskDispatchResponse)
async def dispatch_task_endpoint(
    body: TaskDispatchRequest,
    caller_device_id: str = Depends(verify_dlc_api_token),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> TaskDispatchResponse | JSONResponse:
    """Generate a motion path and dispatch it to the target device."""
    if body.device_id != caller_device_id:
        return TaskDispatchResponse(status="rejected", error="device_id mismatch")

    limited = check_key_limit(f"dlc_dispatch:{caller_device_id}", _quota_for(body.type))
    if limited is not None:
        return limited

    # S10: dedupe replays — a repeated Idempotency-Key must not dispatch twice.
    idem_full_key = f"{caller_device_id}:{idempotency_key}" if idempotency_key else None
    if idem_full_key:
        try:
            claimed = _claim_idempotency_key(idem_full_key, body.request_id)
        except IdempotencyUnavailableError:
            return JSONResponse(
                status_code=503,
                content={"status": "failed", "error": "idempotency store unavailable"},
            )
        if not claimed:
            return TaskDispatchResponse(status="duplicate", error="idempotency key already used")

    # P2-a: the idempotency key is claimed *before* the work runs, so any failure
    # (returned or raised) must release it — see _dispatch_and_release.
    return await _dispatch_and_release(body, idem_full_key)


async def _dispatch_and_release(body: TaskDispatchRequest, idem_full_key: str | None) -> TaskDispatchResponse:
    """Build the motion payload and dispatch it, releasing the idempotency key on
    any failure path (returned failure, unsupported type, raised exception, or a
    rejected dispatch) so the caller can retry with the same Idempotency-Key.
    Only a dispatch that actually reached the device queue keeps the key."""
    try:
        result, motion_task = await _build_dispatch_payload(body)
        if result.get("status") != "success":
            if idem_full_key:
                _release_idempotency_key(idem_full_key, body.request_id)
            return TaskDispatchResponse(status="failed", error=result.get("error"))
        if motion_task is None:
            if idem_full_key:
                _release_idempotency_key(idem_full_key, body.request_id)
            return TaskDispatchResponse(status="failed", error="unsupported type")

        dispatch_result = await dispatch_task(body.device_id, motion_task)
    except Exception:
        # Command never reached the device queue — release so the caller can retry.
        if idem_full_key:
            _release_idempotency_key(idem_full_key, body.request_id)
        raise
    # Keep claim for any accepted queue state (incl. honest no-delivery queue).
    # Keep claim for accepted delivery states (sent online push, queued, or offline hold).
    if idem_full_key and dispatch_result.get("status") not in {
        "sent",
        "queued",
        "queued_no_delivery",
    }:
        _release_idempotency_key(idem_full_key, body.request_id)
    return TaskDispatchResponse(
        status=dispatch_result["status"],
        task_id=dispatch_result.get("task_id"),
        queue_depth=dispatch_result.get("queue_depth", 0),
        error=(
            QUEUED_NO_DELIVERY_USER_MESSAGE
            if dispatch_result.get("status") == QUEUED_NO_DELIVERY_STATUS
            else dispatch_result.get("error")
        ),
    )


@router.post("/dlc/tasks/validate", response_model=TaskValidateResponse)
async def validate_task(
    body: TaskValidateRequest,
    caller_device_id: str = Depends(verify_dlc_api_token),
) -> TaskValidateResponse:
    """Validate a motion path against workspace bounds and safety rules."""
    result = validate_path(body.path, workspace=body.workspace)
    return TaskValidateResponse(**result)
