"""Device memory admin routes for parent/operator control."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from access_guard import require_private_api_key
from device_memory import (
    MemoryEntry,
    MemoryStore,
    MemoryType,
    consolidate_task_episodes,
    get_device_failure_warnings,
    recall_planner_hints,
)
from device_memory.quality_gates import is_safe_for_recall
from routes.json_body import read_json_object

router = APIRouter(prefix="/device/v1/memory", tags=["device-memory"])
_log = logging.getLogger(__name__)

_store = MemoryStore()


def get_memory_store() -> MemoryStore:
    return _store


def inject_memory_store(store: MemoryStore) -> None:
    global _store
    _store = store


# ── Recall ───────────────────────────────────────────────────────────


@router.get("/{device_id}/hints", dependencies=[Depends(require_private_api_key)])
async def get_planner_hints(device_id: str) -> dict[str, Any]:
    """Retrieve active memory hints for the planner."""
    hints = recall_planner_hints(_store, device_id)
    return JSONResponse({"device_id": device_id, "hints": hints})


@router.get("/{device_id}/warnings", dependencies=[Depends(require_private_api_key)])
async def get_warnings(device_id: str) -> dict[str, Any]:
    """Retrieve active failure warnings for a device."""
    warnings = get_device_failure_warnings(_store, device_id)
    return JSONResponse({"device_id": device_id, "warnings": warnings})


# ── Admin controls ───────────────────────────────────────────────────


@router.get("/{device_id}/list", dependencies=[Depends(require_private_api_key)])
async def list_memories(device_id: str) -> dict[str, Any]:
    """List all memories for a device."""
    entries = _store.list_by_device(device_id, include_expired=False)
    return JSONResponse({
        "device_id": device_id,
        "count": len(entries),
        "entries": [e.model_dump() for e in entries],
    })


@router.delete("/{device_id}/reset", dependencies=[Depends(require_private_api_key)])
async def reset_memories(device_id: str) -> dict[str, Any]:
    """Delete all memories for a device."""
    count = _store.reset(device_id)
    _log.info("memory reset device_id=%s count=%s", device_id, count)
    return JSONResponse({"device_id": device_id, "deleted": count})


@router.post("/{device_id}/disable", dependencies=[Depends(require_private_api_key)])
async def disable_memory(device_id: str, request: Request) -> dict[str, Any]:
    """Disable a specific memory entry."""
    body = await read_json_object(request, openai_error=False)
    if isinstance(body, JSONResponse):
        return body
    entry_id = body.get("entry_id", "")
    if not entry_id:
        raise HTTPException(400, "entry_id required")
    ok = _store.disable(entry_id)
    return JSONResponse({"device_id": device_id, "entry_id": entry_id, "disabled": ok})


@router.post("/{device_id}/export", dependencies=[Depends(require_private_api_key)])
async def export_memories(device_id: str) -> dict[str, Any]:
    """Export all memories for a device as JSON."""
    data = _store.export(device_id)
    return JSONResponse({"device_id": device_id, "data": data})


@router.post("/{device_id}/consolidate", dependencies=[Depends(require_private_api_key)])
async def trigger_consolidation(device_id: str) -> dict[str, Any]:
    """Trigger episode consolidation for a device."""
    results = consolidate_task_episodes(_store, device_id)
    return JSONResponse({
        "device_id": device_id,
        "consolidated": len(results),
        "entries": [e.model_dump() for e in results],
    })
