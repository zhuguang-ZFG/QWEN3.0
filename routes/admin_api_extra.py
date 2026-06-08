"""Extra admin API endpoints for the redesigned admin panel.

Provides: fallback-analysis, key-url-inventory, retrain-jobs, agent-tasks,
config import/export, devices, alerts, client-keys, SSE log stream.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from routes.admin_auth import verify_admin, verify_csrf
from routes.admin_state import FALLBACK_LOG, stats_context

router = APIRouter()
_log = logging.getLogger(__name__)

# ── Backend PUT (edit) ───────────────────────────────────────────────────────


@router.put("/api/backends/{name}", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def admin_edit_backend(name: str, req: Request):
    """Update an existing backend's URL, model, caps, or admission policy."""
    try:
        import smart_router
    except ImportError:
        raise HTTPException(503, "smart_router not available")
    if name not in smart_router.BACKENDS:
        raise HTTPException(404, f"backend '{name}' not found")
    body = await req.json()
    cfg = smart_router.BACKENDS[name]
    for field in ("url", "model"):
        if field in body and body[field]:
            cfg[field] = body[field]
    if "caps" in body and isinstance(body["caps"], list):
        cfg["caps"] = body["caps"]
    if "admission" in body:
        cfg["admission"] = body["admission"]
    return {"ok": True, "name": name}


# ── Fallback Analysis ─────────────────────────────────────────────────────────


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
            key=lambda x: -x["count"],
        ),
        "by_intent": sorted(
            [{"intent": k, "count": v} for k, v in by_intent.items()],
            key=lambda x: -x["count"],
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


# ── Key-URL Inventory ─────────────────────────────────────────────────────────


@router.get("/api/key-url-inventory", dependencies=[Depends(verify_admin)])
async def key_url_inventory():
    """List all backends with their URL, key status, and provider key pools."""
    try:
        import smart_router
    except ImportError:
        return {"backends": [], "key_pools": {"providers": {}}}

    backends = []
    for name, cfg in smart_router.BACKENDS.items():
        key = cfg.get("key", "")
        masked = (key[:4] + "..." + key[-4:]) if key and len(key) > 8 else ("已配置" if key else "")
        backends.append({
            "name": name,
            "url": cfg.get("url", ""),
            "key_configured": bool(key),
            "key_masked": masked,
            "model": cfg.get("model", ""),
            "fmt": cfg.get("fmt", "openai"),
        })

    # Provider key pools (if key_pool module available)
    providers: dict[str, Any] = {}
    try:
        from key_pool import get_pool_status
        providers = get_pool_status()
    except (ImportError, AttributeError):
        pass

    return {"backends": backends, "key_pools": {"providers": providers}}


# ── Retrain Jobs ──────────────────────────────────────────────────────────────


@router.get("/api/retrain/jobs", dependencies=[Depends(verify_admin)])
async def retrain_jobs():
    """List recent retrain job history."""
    from routes.admin_api import _RETRAIN_JOBS

    jobs = sorted(
        _RETRAIN_JOBS.values(),
        key=lambda j: j.get("started_at", 0),
        reverse=True,
    )
    return {"jobs": jobs[:20]}


# ── Agent Tasks ───────────────────────────────────────────────────────────────


@router.get("/api/agent-tasks", dependencies=[Depends(verify_admin)])
async def admin_agent_tasks(limit: int = 100):
    """List agent tasks with status summary."""
    store = _get_task_store()
    if not store:
        return {"tasks": [], "count": 0}
    raw = store.values() if hasattr(store, 'values') else (store if isinstance(store, dict) else [])
    tasks = sorted(
        raw,
        key=lambda t: t.get("created_at", 0) if isinstance(t, dict) else 0,
        reverse=True,
    )[:limit]
    result = []
    for t in tasks:
        req = t.get("request", {}) if isinstance(t, dict) else {}
        result.append({
            "task_id": t.get("task_id", t.get("id", "")) if isinstance(t, dict) else "",
            "status": t.get("status", "unknown") if isinstance(t, dict) else "unknown",
            "created_at": t.get("created_at", 0) if isinstance(t, dict) else 0,
            "description": (req.get("goal", "") or req.get("description", ""))[:200],
            "worker_id": t.get("worker_id", t.get("claim", {}).get("worker_id", "")) if isinstance(t, dict) else "",
            "backend": t.get("backend", "") if isinstance(t, dict) else "",
        })
    return {"tasks": result, "count": len(result)}


@router.get("/api/agent-tasks/{task_id}", dependencies=[Depends(verify_admin)])
async def admin_agent_task_detail(task_id: str):
    store = _get_task_store()
    if not store:
        raise HTTPException(404, "Task store not available")
    task = store.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return task


@router.post("/api/agent-tasks/{task_id}/cancel", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def admin_cancel_agent_task(task_id: str):
    store = _get_task_store()
    if not store or not hasattr(store, 'get'):
        raise HTTPException(404, "Task store not available")
    task = store.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    task["status"] = "cancel_requested"
    task["updated_at"] = time.time()
    return {"ok": True, "task_id": task_id, "status": "cancel_requested"}


@router.post("/api/agent-tasks/{task_id}/retry", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def admin_retry_agent_task(task_id: str):
    store = _get_task_store()
    if not store or not hasattr(store, 'get'):
        raise HTTPException(404, "Task store not available")
    task = store.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    task["status"] = "pending"
    task["updated_at"] = time.time()
    return {"ok": True, "task_id": task_id, "status": "pending"}


def _get_task_store():
    try:
        from routes.agent_tasks import _store
        return _store
    except (ImportError, AttributeError):
        return None


# ── Config Export/Import ──────────────────────────────────────────────────────

_REPO_ROOT = Path(__file__).resolve().parent.parent


@router.get("/api/config/export", dependencies=[Depends(verify_admin)])
async def config_export():
    """Export current backend configuration summary."""
    config: dict[str, Any] = {"version": "1.0", "exported_at": time.time()}
    try:
        import smart_router
        config["backends"] = {
            name: {
                "url": cfg.get("url", ""),
                "model": cfg.get("model", ""),
                "fmt": cfg.get("fmt", "openai"),
                "tier": cfg.get("tier", ""),
                "caps": cfg.get("caps", []),
            }
            for name, cfg in smart_router.BACKENDS.items()
        }
    except ImportError:
        config["backends"] = {}
    _stats, _lock, backend_enabled = stats_context()
    config["backend_enabled"] = dict(backend_enabled)
    return config


@router.post("/api/config/import", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def config_import(req: Request):
    body = await req.json()
    if not body.get("version"):
        raise HTTPException(400, "Invalid config format: missing version")
    imported: list[str] = []
    try:
        import smart_router
        new_backends = body.get("backends", {})
        for name, cfg in new_backends.items():
            if name not in smart_router.BACKENDS:
                smart_router.BACKENDS[name] = cfg
                imported.append(name)
    except ImportError:
        pass
    return {"ok": True, "imported": imported}


# ── Devices ───────────────────────────────────────────────────────────────────


@router.get("/api/devices", dependencies=[Depends(verify_admin)])
async def admin_devices():
    """List known devices from device gateway."""
    try:
        from device_gateway.registry import get_all_devices
        devices = get_all_devices()
        return {"devices": devices}
    except (ImportError, AttributeError):
        pass
    try:
        from device_gateway.store import task_store_health
        return {"devices": [], "_note": "task_store only: " + str(task_store_health())}
    except ImportError:
        return {"devices": []}


@router.get("/api/devices/{device_id}", dependencies=[Depends(verify_admin)])
async def admin_device_detail(device_id: str):
    try:
        from device_gateway.registry import get_device
        dev = get_device(device_id)
        if not dev:
            raise HTTPException(404, "Device not found")
        return dev
    except ImportError:
        raise HTTPException(503, "Device gateway not available")


@router.post("/api/devices/{device_id}/restart", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def admin_restart_device(device_id: str):
    try:
        from device_gateway.registry import restart_device
        await restart_device(device_id)
        return {"ok": True, "device_id": device_id}
    except ImportError:
        raise HTTPException(503, "Device gateway not available")


# ── Alerts ────────────────────────────────────────────────────────────────────

_ALERT_RULES: dict[str, dict[str, Any]] = {}


@router.get("/api/alerts/rules", dependencies=[Depends(verify_admin)])
async def list_alert_rules():
    return {"rules": list(_ALERT_RULES.values())}


@router.post("/api/alerts/rules", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def create_alert_rule(req: Request):
    body = await req.json()
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(400, "name required")
    rule_id = f"alert-{uuid.uuid4().hex[:8]}"
    rule = {
        "rule_id": rule_id,
        "name": name,
        "metric": body.get("metric", "error_rate"),
        "condition": body.get("condition", "gt"),
        "threshold": float(body.get("threshold", 0.5)),
        "window_sec": int(body.get("window_sec", 300)),
        "enabled": True,
        "created_at": time.time(),
    }
    _ALERT_RULES[rule_id] = rule
    return {"ok": True, "rule": rule}


@router.put("/api/alerts/rules/{rule_id}", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def update_alert_rule(rule_id: str, req: Request):
    body = await req.json()
    rule = _ALERT_RULES.get(rule_id)
    if not rule:
        raise HTTPException(404, "Rule not found")
    if "enabled" in body:
        rule["enabled"] = bool(body["enabled"])
    if "threshold" in body:
        rule["threshold"] = float(body["threshold"])
    if "name" in body:
        rule["name"] = body["name"]
    return {"ok": True, "rule": rule}


@router.delete("/api/alerts/rules/{rule_id}", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def delete_alert_rule(rule_id: str):
    if rule_id not in _ALERT_RULES:
        raise HTTPException(404, "Rule not found")
    del _ALERT_RULES[rule_id]
    return {"ok": True, "rule_id": rule_id}


# ── Client Keys ───────────────────────────────────────────────────────────────

_CLIENT_KEYS: dict[str, dict[str, Any]] = {}


@router.get("/api/client-keys", dependencies=[Depends(verify_admin)])
async def list_client_keys():
    return {"keys": list(_CLIENT_KEYS.values())}


@router.post("/api/client-keys", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def create_client_key(req: Request):
    body = await req.json()
    label = body.get("label", "").strip()
    if not label:
        raise HTTPException(400, "label required")
    key_id = uuid.uuid4().hex[:16]
    key_value = f"lima-{uuid.uuid4().hex}"
    masked = key_value[:8] + "..." + key_value[-4:]
    entry = {
        "key_id": key_id,
        "key_masked": masked,
        "label": label,
        "enabled": True,
        "quota_daily": int(body.get("quota_daily", 1000)),
        "quota_monthly": int(body.get("quota_monthly", 30000)),
        "usage_daily": 0,
        "usage_monthly": 0,
        "rate_limit_rpm": int(body.get("rate_limit_rpm", 20)),
        "allowed_urls": body.get("allowed_urls", ["*"]),
        "last_used_at": 0,
        "created_at": time.time(),
    }
    _CLIENT_KEYS[key_id] = entry
    return {"ok": True, "key_value": key_value, "key": entry}


@router.put("/api/client-keys/{key_id}", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def update_client_key(key_id: str, req: Request):
    body = await req.json()
    entry = _CLIENT_KEYS.get(key_id)
    if not entry:
        raise HTTPException(404, "Key not found")
    for field in ("label", "enabled", "quota_daily", "quota_monthly", "rate_limit_rpm", "allowed_urls"):
        if field in body:
            entry[field] = body[field]
    return {"ok": True, "key": entry}


@router.delete("/api/client-keys/{key_id}", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def delete_client_key(key_id: str):
    if key_id not in _CLIENT_KEYS:
        raise HTTPException(404, "Key not found")
    del _CLIENT_KEYS[key_id]
    return {"ok": True}


@router.post("/api/client-keys/{key_id}/regenerate", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def regenerate_client_key(key_id: str):
    entry = _CLIENT_KEYS.get(key_id)
    if not entry:
        raise HTTPException(404, "Key not found")
    key_value = f"lima-{uuid.uuid4().hex}"
    entry["key_masked"] = key_value[:8] + "..." + key_value[-4:]
    entry["regenerated_at"] = time.time()
    return {"ok": True, "key_value": key_value}


# ── SSE Live Log Stream ──────────────────────────────────────────────────────

_SSE_SUBSCRIBERS: list[asyncio.Queue] = []


def broadcast_log(entry: dict) -> None:
    """Push a log entry to all SSE subscribers."""
    dead: list[asyncio.Queue] = []
    for q in _SSE_SUBSCRIBERS:
        try:
            q.put_nowait(entry)
        except asyncio.QueueFull:
            dead.append(q)
    for q in dead:
        _SSE_SUBSCRIBERS.remove(q)


@router.get("/api/logs/stream", dependencies=[Depends(verify_admin)])
async def log_stream():
    """SSE endpoint: streams new log entries in real time."""
    queue: asyncio.Queue = asyncio.Queue(maxsize=200)
    _SSE_SUBSCRIBERS.append(queue)

    async def event_generator():
        try:
            while True:
                try:
                    entry = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {json.dumps(entry)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            if queue in _SSE_SUBSCRIBERS:
                _SSE_SUBSCRIBERS.remove(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
