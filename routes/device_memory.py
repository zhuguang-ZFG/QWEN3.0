"""Device memory admin routes for parent/operator control."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from access_guard import require_private_api_key
from device_memory import (
    consolidate_task_episodes,
    get_device_failure_warnings,
    recall_planner_hints,
)
from device_memory.store import get_memory_store, inject_memory_store
from routes.json_body import read_json_object

router = APIRouter(prefix="/device/v1/memory", tags=["device-memory"])
_log = logging.getLogger(__name__)

__all__ = ["get_memory_store", "inject_memory_store", "router"]

# ── Recall ───────────────────────────────────────────────────────────


@router.get("/{device_id}/hints", dependencies=[Depends(require_private_api_key)])
async def get_planner_hints(device_id: str) -> JSONResponse:
    """Retrieve active memory hints for the planner."""
    store = get_memory_store()
    hints = recall_planner_hints(store, device_id)
    return JSONResponse({"device_id": device_id, "hints": hints})


@router.get("/{device_id}/warnings", dependencies=[Depends(require_private_api_key)])
async def get_warnings(device_id: str) -> JSONResponse:
    """Retrieve active failure warnings for a device."""
    store = get_memory_store()
    warnings = get_device_failure_warnings(store, device_id)
    return JSONResponse({"device_id": device_id, "warnings": warnings})


# ── Admin controls ───────────────────────────────────────────────────


@router.get("/{device_id}/list", dependencies=[Depends(require_private_api_key)])
async def list_memories(device_id: str) -> JSONResponse:
    """List all memories for a device."""
    store = get_memory_store()
    entries = store.list_by_device(device_id, include_expired=False)
    return JSONResponse(
        {
            "device_id": device_id,
            "count": len(entries),
            "entries": [e.model_dump() for e in entries],
        }
    )


@router.delete("/{device_id}/reset", dependencies=[Depends(require_private_api_key)])
async def reset_memories(device_id: str) -> JSONResponse:
    """Delete all memories for a device."""
    store = get_memory_store()
    count = store.reset(device_id)
    _log.info("memory reset device_id=%s count=%s", device_id, count)
    return JSONResponse({"device_id": device_id, "deleted": count})


@router.post("/{device_id}/disable", dependencies=[Depends(require_private_api_key)])
async def disable_memory(device_id: str, request: Request) -> JSONResponse:
    """Disable a specific memory entry."""
    body = await read_json_object(request, openai_error=False)
    if isinstance(body, JSONResponse):
        return body
    entry_id = body.get("entry_id", "")
    if not entry_id:
        raise HTTPException(400, "entry_id required")
    store = get_memory_store()
    ok = store.disable(entry_id)
    return JSONResponse({"device_id": device_id, "entry_id": entry_id, "disabled": ok})


@router.post("/{device_id}/export", dependencies=[Depends(require_private_api_key)])
async def export_memories(device_id: str) -> JSONResponse:
    """Export all memories for a device as JSON."""
    store = get_memory_store()
    data = store.export(device_id)
    return JSONResponse({"device_id": device_id, "data": data})


@router.post("/{device_id}/consolidate", dependencies=[Depends(require_private_api_key)])
async def trigger_consolidation(device_id: str) -> JSONResponse:
    """Trigger episode consolidation for a device."""
    store = get_memory_store()
    results = consolidate_task_episodes(store, device_id)
    return JSONResponse(
        {
            "device_id": device_id,
            "consolidated": len(results),
            "entries": [e.model_dump() for e in results],
        }
    )
