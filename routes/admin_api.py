"""Admin JSON API routes (CQ-014 slice 11)."""

from __future__ import annotations

import json
import logging
import os
import time

from fastapi import APIRouter, Depends, HTTPException, Request

from backends_registry import BACKENDS, add_backend, has_backend, remove_backend
import health_tracker
from device_gateway.family_gate import (
    approve_family,
    list_family_approvals,
    revoke_family,
)
from routes.admin_auth import verify_admin, verify_csrf
from routes.admin_backends import (
    _is_safe_backend_url,
    describe_backend,
    test_backend_sync,
)
from routes.admin_state import FALLBACK_LOG, stats_context
from routes.ops_metrics import backend_call_detail

router = APIRouter()
_log = logging.getLogger(__name__)


@router.get("/api/stats", dependencies=[Depends(verify_admin)])
async def admin_stats():
    stats, lock, _enabled = stats_context()
    with lock:
        uptime = int(time.time() - stats["start_time"])
        total = stats["total_requests"]
        backend_calls = {name: backend_call_detail(value) for name, value in dict(stats["backend_calls"]).items()}
        avg_ms = 0
        if total > 0:
            total_ms_all = sum(item["total_ms"] for item in backend_calls.values())
            avg_ms = int(total_ms_all / total)
        ips = set()
        ide_dist = {}
        for log in stats["recent_logs"]:
            if log.get("ip"):
                ips.add(log["ip"])
            ide = log.get("ide", "未知")
            ide_dist[ide] = ide_dist.get(ide, 0) + 1
        return {
            "total_requests": total,
            "uptime_seconds": uptime,
            "avg_response_ms": avg_ms,
            "backend_calls": backend_calls,
            "intent_distribution": dict(stats["intent_distribution"]),
            "unique_ips": len(ips),
            "ide_distribution": ide_dist,
        }


@router.get("/api/logs", dependencies=[Depends(verify_admin)])
async def admin_logs():
    stats, lock, _enabled = stats_context()
    with lock:
        return list(reversed(stats["recent_logs"][-10:]))


@router.get("/api/retrieval-traces", dependencies=[Depends(verify_admin)])
async def admin_retrieval_traces():
    try:
        from context_pipeline.retrieval_trace import get_recent_traces

        return get_recent_traces(limit=20)
    except ImportError:
        return []


@router.get("/api/backends", dependencies=[Depends(verify_admin)])
async def admin_backends():
    _stats, _lock, backend_enabled = stats_context()
    backends_list = []
    for name, cfg in BACKENDS.items():
        enabled = backend_enabled.get(name, True)
        backends_list.append(
            describe_backend(
                name,
                cfg,
                enabled=enabled,
                status_info=_backend_status_info(name),
            )
        )
    return backends_list


def _backend_status_info(name: str) -> dict:
    """Build admin-backend status compatible with the old circuit-breaker shape."""
    import health_state

    quality = health_state.get_backend_quality(name)
    total = quality["total_requests"]
    errors = quality["empty_count"] + quality["error_msg_count"]
    error_rate = f"{errors / total:.1%}" if total > 0 else "0.0%"
    return {
        "state": "open" if health_tracker.is_cooled_down(name) else "closed",
        "total_calls": total,
        "error_rate": error_rate,
    }


@router.post("/api/backends", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def admin_add_backend(req: Request):
    _stats, _lock, backend_enabled = stats_context()
    body = await req.json()
    name = body.get("name", "").strip()
    url = body.get("url", "").strip()
    key = body.get("key", "").strip()
    model = body.get("model", name)
    fmt = body.get("fmt", "openai")
    auth = body.get("auth", "").strip()
    if not auth:
        auth = "x-api-key" if fmt == "anthropic" else "bearer"
    if not name or not url:
        raise HTTPException(400, "name and url required")
    if not _is_safe_backend_url(url):
        raise HTTPException(400, f"backend URL must be a public HTTPS endpoint: {url}")
    if has_backend(name):
        raise HTTPException(409, f"backend '{name}' already exists")
    add_backend(name, {
        "url": url,
        "key": key,
        "model": model,
        "fmt": fmt,
        "auth": auth,
        "tier": body.get("tier", ""),
        "caps": body.get("caps", []),
    })
    backend_enabled[name] = True
    try:
        test_result = test_backend_sync(name)
        return {"ok": True, "message": f"backend '{name}' added", "test": test_result}
    except Exception as exc:
        backend_enabled[name] = False
        return {
            "ok": True,
            "message": f"backend '{name}' added but DISABLED (test failed: {exc})",
            "enabled": False,
        }


@router.delete("/api/backends/{name}", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def admin_delete_backend(name: str):
    _stats, _lock, backend_enabled = stats_context()
    if not has_backend(name):
        raise HTTPException(404, f"backend '{name}' not found")
    remove_backend(name)
    backend_enabled.pop(name, None)
    return {"ok": True, "message": f"backend '{name}' deleted"}


@router.post("/api/backends/{name}/toggle", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def admin_toggle_backend(name: str):
    _stats, _lock, backend_enabled = stats_context()
    if name not in BACKENDS:
        raise HTTPException(404, f"backend '{name}' not found")
    current = backend_enabled.get(name, True)
    backend_enabled[name] = not current
    return {"ok": True, "enabled": not current}


@router.post("/api/backends/{name}/test", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def admin_test_backend(name: str):
    if name not in BACKENDS:
        raise HTTPException(404, f"backend '{name}' not found")
    return test_backend_sync(name)


@router.get("/api/model-status", dependencies=[Depends(verify_admin)])
async def admin_model_status():
    log_count = 0
    recent_logs = []
    if os.path.exists(FALLBACK_LOG):
        with open(FALLBACK_LOG, encoding="utf-8") as handle:
            lines = handle.readlines()
        log_count = len(lines)
        for line in lines[-50:]:
            try:
                recent_logs.append(json.loads(line.strip()))
            except Exception as exc:
                _log.warning("skip malformed fallback log line: %s", exc)
    return {
        "model": "Round 12 (Qwen3-1.7B)",
        "accuracy": "89.7%",
        "data_count": 3190,
        "fallback_log_count": log_count,
        "threshold": 100,
        "recent_fallbacks": recent_logs,
    }


@router.get("/api/devices/{device_id}/families", dependencies=[Depends(verify_admin)])
async def admin_list_family_approvals(device_id: str):
    """List per-device protocol-family approval status."""
    approvals = list_family_approvals(device_id)
    return {
        "deviceId": device_id,
        "families": [
            {
                "family": a.family,
                "status": a.status,
                "approvedBy": a.approved_by,
                "approvedAt": a.approved_at,
                "revokedAt": a.revoked_at,
                "evidence": a.evidence,
            }
            for a in approvals
        ],
    }


@router.post(
    "/api/devices/{device_id}/families/{family}/approve",
    dependencies=[Depends(verify_admin), Depends(verify_csrf)],
)
async def admin_approve_family(device_id: str, family: str, request: Request):
    """Approve a protocol family for a specific device."""
    body = await request.json()
    evidence = body.get("evidence") if isinstance(body.get("evidence"), dict) else {}
    account_id = body.get("approvedBy", "admin")
    record = approve_family(device_id, family, approved_by=account_id, evidence=evidence)
    return {
        "deviceId": record.device_id,
        "family": record.family,
        "status": record.status,
        "approvedBy": record.approved_by,
        "approvedAt": record.approved_at,
    }


@router.post(
    "/api/devices/{device_id}/families/{family}/revoke",
    dependencies=[Depends(verify_admin), Depends(verify_csrf)],
)
async def admin_revoke_family(device_id: str, family: str):
    """Revoke a protocol-family approval for a specific device."""
    record = revoke_family(device_id, family, revoked_by="admin")
    if record is None:
        raise HTTPException(404, f"no approval found for {family} on {device_id}")
    return {
        "deviceId": record.device_id,
        "family": record.family,
        "status": record.status,
        "revokedAt": record.revoked_at,
    }
