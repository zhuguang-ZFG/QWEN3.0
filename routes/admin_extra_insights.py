"""Admin API: fallback analysis, key inventory, retrain jobs."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from fastapi import APIRouter, Depends

from routes.facade import BACKENDS
from routes.admin_auth import verify_admin
from routes.admin_state import FALLBACK_LOG

router = APIRouter()
_log = logging.getLogger(__name__)


@router.get("/api/fallback-analysis", dependencies=[Depends(verify_admin)])
async def fallback_analysis():
    """Aggregated fallback statistics: by backend, by intent, hourly trend."""
    entries = _read_fallback_entries()
    by_backend: dict[str, int] = {}
    by_intent: dict[str, int] = {}
    hourly: dict[str, int] = {}
    for e in entries:
        be = e.get("original_backend") or e.get("backend") or "unknown"
        by_backend[be] = by_backend.get(be, 0) + 1
        intent = e.get("intent") or e.get("reason") or "unknown"
        by_intent[intent] = by_intent.get(intent, 0) + 1
        ts = e.get("timestamp") or e.get("time") or ""
        hour = str(ts)[:13] if ts else "unknown"
        hourly[hour] = hourly.get(hour, 0) + 1
    return {
        "total": len(entries),
        "by_backend": sorted(
            [{"backend": k, "count": v} for k, v in by_backend.items()],
            key=lambda x: x["count"],
            reverse=True,
        ),
        "by_intent": sorted(
            [{"intent": k, "count": v} for k, v in by_intent.items()],
            key=lambda x: x["count"],
            reverse=True,
        ),
        "hourly_trend": sorted(
            [{"hour": k, "count": v} for k, v in hourly.items()],
            key=lambda x: x["hour"],
        ),
    }


def _read_fallback_entries() -> list[dict]:
    if not os.path.exists(FALLBACK_LOG):
        return []
    entries: list[dict] = []
    try:
        with open(FALLBACK_LOG, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except OSError:
        _log.warning("failed to read fallback log: %s", FALLBACK_LOG)
    return entries


@router.get("/api/key-url-inventory", dependencies=[Depends(verify_admin)])
async def key_url_inventory():
    """List all backends with their URL, key status, and provider key pools."""
    backend_list = []
    for name, cfg in BACKENDS.items():
        key = cfg.get("key", "")
        masked = (key[:4] + "..." + key[-4:]) if key and len(key) > 8 else ("已配置" if key else "")
        backend_list.append(
            {
                "name": name,
                "url": cfg.get("url", ""),
                "key_configured": bool(key),
                "key_masked": masked,
                "model": cfg.get("model", ""),
                "fmt": cfg.get("fmt", "openai"),
            }
        )

    providers: dict[str, Any] = {}
    try:
        from key_pool import get_pool_status

        providers = get_pool_status()
    except (ImportError, AttributeError):
        pass

    return {"backends": backend_list, "key_pools": {"providers": providers}}


@router.get("/api/retrain/jobs", dependencies=[Depends(verify_admin)])
async def retrain_jobs():
    """List recent retrain job history.

    The legacy ``auto_retrain.py`` scheduler was retired in Phase 0; this
    endpoint is kept for admin UI compatibility and always returns an empty
    list.
    """
    return {"jobs": []}


@router.post("/api/retrain", dependencies=[Depends(verify_admin)])
async def trigger_retrain():
    """Manual trigger for the retired auto-retrain pipeline."""
    return {
        "status": "retired",
        "message": "auto_retrain was retired in Phase 0; manual retraining is no longer supported.",
    }


@router.get("/api/agent-audit", dependencies=[Depends(verify_admin)])
async def agent_audit(limit: int = 50):
    """Legacy agent audit endpoint retained for admin UI compatibility."""
    return {"tasks": []}
