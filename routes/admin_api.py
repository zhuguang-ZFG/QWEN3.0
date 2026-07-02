"""Admin JSON API routes (CQ-014 slice 11)."""

from __future__ import annotations

import json
import logging
import os
import time

from fastapi import APIRouter, Depends, HTTPException, Request

# Re-exports used by ``routes.admin_backends_routes`` via ``import routes.admin_api as _a``
# lazy access (see comment in that module). Kept with noqa to allow patch.setattr on the alias.
from routes.facade import (  # noqa: F401
    BACKENDS,
    add_backend,
    has_backend,
    health_tracker,
    remove_backend,
)
from device_gateway.family_approval_store import (
    approve_family,
    list_family_approvals,
    revoke_family,
)
from routes.admin_auth import verify_admin, verify_csrf
from routes.admin_backends import (  # noqa: F401
    _is_safe_backend_url,
    describe_backend,
    test_backend_sync,
)
from routes.admin_state import FALLBACK_LOG, stats_context
from routes.client_keys_store import load_keys
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
        keys = load_keys()
        key_summary = [
            {
                "key_id": k["key_id"],
                "label": k["label"],
                "enabled": k["enabled"],
                "usage_daily": k["usage_daily"],
                "usage_monthly": k["usage_monthly"],
                "quota_daily": k["quota_daily"],
                "quota_monthly": k["quota_monthly"],
            }
            for k in keys.values()
        ]
        return {
            "total_requests": total,
            "uptime_seconds": uptime,
            "avg_response_ms": avg_ms,
            "backend_calls": backend_calls,
            "intent_distribution": dict(stats["intent_distribution"]),
            "unique_ips": len(ips),
            "ide_distribution": ide_dist,
            "client_keys": key_summary,
        }


@router.get("/api/logs", dependencies=[Depends(verify_admin)])
async def admin_logs():
    stats, lock, _enabled = stats_context()
    with lock:
        return list(reversed(stats["recent_logs"][-10:]))


from routes.admin_backends_routes import router as backends_router

router.include_router(backends_router)


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
