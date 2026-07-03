"""LiMa device gateway events route.

Extracted from ``routes.device_gateway`` (S batch deep-slim) so the main
module owns task writes, ws/ticket, and ws while this module owns the
single POST ``/events`` endpoint (motion_event / device_info / self_check
uplink processing). Shares the ``/device/v1`` prefix with the main router;
FastAPI merges same-prefix routers without conflict.

``shadow_store`` and ``process_motion_event_core`` are stable module-level
singletons (no ``set_*_for_tests`` swap interface), so top-level imports
are safe here — unlike the ``task_store`` deferred-import pattern required
in ``device_gateway_query_routes`` (R batch lesson).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from access_guard import require_private_api_key
from device_gateway.protocol import ProtocolError, ack_frame, error_frame, validate_uplink
from device_gateway.task_events import process_motion_event_core
from device_intelligence.shadow import shadow_store
from routes.json_body import read_json_object

router = APIRouter(prefix="/device/v1")


@router.post("/events", dependencies=[Depends(require_private_api_key)])
async def device_gateway_events(request: Request) -> JSONResponse:
    body = await read_json_object(request)
    if isinstance(body, JSONResponse):
        return body
    try:
        message = validate_uplink(body)
    except ProtocolError as exc:
        return JSONResponse(status_code=400, content=error_frame(exc))

    msg_type = message["type"]
    device_id = message.get("device_id", "")
    if msg_type == "motion_event":
        summary = process_motion_event_core(device_id, message)
        return JSONResponse(ack_frame("motion_event_ack", device_id, **summary, request_id=message.get("request_id")))
    if msg_type == "device_info":
        shadow_store.update_device_info(message)
        return JSONResponse(ack_frame("device_info_ack", device_id, request_id=message.get("request_id")))
    if msg_type == "self_check":
        shadow_store.update_self_check(message)
        return JSONResponse(
            ack_frame(
                "self_check_ack",
                device_id,
                status=message.get("status", "unknown"),
                request_id=message.get("request_id"),
            )
        )
    return JSONResponse(
        status_code=400,
        content=error_frame(
            ProtocolError("E_UNSUPPORTED_TYPE", "event type is not supported", message.get("request_id"))
        ),
    )
