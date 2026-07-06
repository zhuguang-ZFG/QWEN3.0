"""dlc_api P1 routes: /dlc/tasks/* contract for device drawing/writing."""

from __future__ import annotations

import ipaddress
import logging
import socket
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Header, HTTPException

from config.settings import DEVICE
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
from dlc_api.idempotency import claim_idempotency_key as _claim_idempotency_key
from dlc_api.idempotency import release_idempotency_key as _release_idempotency_key
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


# SEC-04: only the gallery image source is permitted for server-side download.
ALLOWED_IMAGE_HOSTS = frozenset({"api.telegram.org"})


def _is_private_ip(value: str) -> bool:
    """Return True if *value* is a private/loopback/link-local/reserved IP literal."""
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved


def _resolve_hostname(hostname: str) -> list[str]:
    """Resolve *hostname* to a list of IP strings (patched in tests)."""
    return [info[4][0] for info in socket.getaddrinfo(hostname, None)]


def _validate_image_url(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return (image_url, error_msg). Exactly one is non-None.

    SEC-04 SSRF hardening, in order:
      1. literal private/loopback/link-local IP → blocked (private)
      2. host not on ALLOWED_IMAGE_HOSTS → rejected (not allowed)
      3. DNS resolves to a private IP (rebinding) → blocked (private)
    """
    image_url = str(payload.get("image_url", "")).strip()
    if not image_url:
        return None, "image_url is required"
    if not image_url.startswith(("https://", "http://")):
        return None, "image_url must be an http(s) URL"
    hostname = urlparse(image_url).hostname or ""

    # 1. Literal private IP address → blocked regardless of allowlist.
    if _is_private_ip(hostname):
        return None, "image_url hostname is blocked (private/loopback/link-local)"

    # 2. Host allowlist: only the gallery source may be fetched server-side.
    if hostname not in ALLOWED_IMAGE_HOSTS:
        return None, f"image_url host not allowed: {hostname}"

    # 3. DNS rebinding guard: reject when the host resolves to a private IP.
    try:
        addrs = _resolve_hostname(hostname)
    except OSError:
        return None, f"image_url host could not be resolved: {hostname}"
    if any(_is_private_ip(addr) for addr in addrs):
        return None, "image_url resolves to a blocked (private) address"

    return image_url, None


def _motion_task(text: str, request_id: str, entrypoint: str) -> dict[str, Any]:
    """Build a motion_task dict for dispatch_task."""
    return {"text": text, "request_id": request_id, "source": "dlc_api", "entrypoint": entrypoint}


def _quota_for(task_type: str) -> int:
    """S3: per-minute quota for a task type. draw_from_image is CPU/cost heavy → lower."""
    if task_type == "draw_from_image":
        return DEVICE.dlc_image_per_min
    return DEVICE.dlc_task_per_min


@router.get("/health")
async def health() -> dict[str, str]:
    """Lightweight health endpoint for load balancers and smoke tests."""
    return {"status": "ok", "service": "dlc-drawing", "version": "0.2.0-p1"}


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
) -> TaskPreviewResponse:
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
        image_url, err = _validate_image_url(body.payload)
        if err:
            return TaskPreviewResponse(status="failed", error=err)
        result = await handle_draw_from_image(image_url, device_id=body.device_id)
        return _preview_from_result(result)

    return TaskPreviewResponse(status="failed", error="unsupported type")


@router.post("/dlc/tasks/dispatch", response_model=TaskDispatchResponse)
async def dispatch_task_endpoint(
    body: TaskDispatchRequest,
    caller_device_id: str = Depends(verify_dlc_api_token),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> TaskDispatchResponse:
    """Generate a motion path and dispatch it to the target device."""
    if body.device_id != caller_device_id:
        return TaskDispatchResponse(status="rejected", error="device_id mismatch")

    limited = check_key_limit(f"dlc_dispatch:{caller_device_id}", _quota_for(body.type))
    if limited is not None:
        return limited

    # S10: dedupe replays — a repeated Idempotency-Key must not dispatch twice.
    idem_full_key = f"{caller_device_id}:{idempotency_key}" if idempotency_key else None
    if idem_full_key and not _claim_idempotency_key(idem_full_key, body.request_id):
        return TaskDispatchResponse(status="duplicate", error="idempotency key already used")

    # P2-a: the idempotency key is claimed *before* the work runs, so any failure
    # below must release it — otherwise a transient failure (device offline, path
    # gen error) permanently burns the key and the client can never retry.
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
    # A rejected/failed dispatch never reached the device queue — release the key
    # so the caller can retry with the same Idempotency-Key.
    if idem_full_key and dispatch_result.get("status") not in {"sent", "queued"}:
        _release_idempotency_key(idem_full_key, body.request_id)
    return TaskDispatchResponse(
        status=dispatch_result["status"],
        task_id=dispatch_result.get("task_id"),
        queue_depth=dispatch_result.get("queue_depth", 0),
        error=dispatch_result.get("error"),
    )


async def _build_dispatch_payload(
    body: TaskDispatchRequest,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Generate path and build motion_task for the given dispatch request.

    Returns (dlc_core_result, motion_task). motion_task is None for unsupported types.
    """
    if body.type == "write_text":
        text = str(body.payload.get("text", "")).strip()
        if not text:
            return {"status": "failed", "error": "text is required"}, None
        result = await handle_write(text)
        return result, _motion_task(f"写{text}", body.request_id, "write_text")

    if body.type == "draw_generated":
        prompt = str(body.payload.get("prompt", "")).strip()
        if not prompt:
            return {"status": "failed", "error": "prompt is required"}, None
        result = await handle_draw(prompt, device_id=body.device_id, allow_dashscope=False)
        return result, _motion_task(f"画{prompt}", body.request_id, "draw_generated")

    if body.type == "draw_from_image":
        image_url, err = _validate_image_url(body.payload)
        if err:
            return {"status": "failed", "error": err}, None
        result = await handle_draw_from_image(image_url, device_id=body.device_id)
        return result, _motion_task("描图", body.request_id, "draw_from_image")

    return {"status": "failed", "error": "unsupported type"}, None


@router.post("/dlc/tasks/validate", response_model=TaskValidateResponse)
async def validate_task(
    body: TaskValidateRequest,
    caller_device_id: str = Depends(verify_dlc_api_token),
) -> TaskValidateResponse:
    """Validate a motion path against workspace bounds and safety rules."""
    result = validate_path(body.path, workspace=body.workspace)
    return TaskValidateResponse(**result)
