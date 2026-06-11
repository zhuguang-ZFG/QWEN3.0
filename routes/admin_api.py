"""Admin JSON API routes (CQ-014 slice 11)."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request

import smart_router
from routes.admin_auth import verify_admin, verify_csrf
from routes.admin_backends import describe_backend, test_backend_sync
from routes.admin_state import FALLBACK_LOG, stats_context
from routes.ops_metrics import backend_call_detail

router = APIRouter()
REPO_ROOT = Path(__file__).resolve().parent.parent
_log = logging.getLogger(__name__)

_RETRAIN_LOCK = asyncio.Lock()
_RETRAIN_JOBS: dict[str, dict[str, object]] = {}
_RETRAIN_TIMEOUT_SEC = int(os.environ.get("LIMA_RETRAIN_TIMEOUT_SEC", "600"))


@router.get("/api/stats", dependencies=[Depends(verify_admin)])
async def admin_stats():
    stats, lock, _enabled = stats_context()
    with lock:
        uptime = int(time.time() - stats["start_time"])
        total = stats["total_requests"]
        backend_calls = {
            name: backend_call_detail(value)
            for name, value in dict(stats["backend_calls"]).items()
        }
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
    cb = smart_router.cb_status()
    backends = []
    for name, cfg in smart_router.BACKENDS.items():
        enabled = backend_enabled.get(name, True)
        backends.append(
            describe_backend(
                name,
                cfg,
                enabled=enabled,
                status_info=cb.get(name, {}),
            )
        )
    return backends


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
    if name in smart_router.BACKENDS:
        raise HTTPException(409, f"backend '{name}' already exists")
    smart_router.BACKENDS[name] = {
        "url": url,
        "key": key,
        "model": model,
        "fmt": fmt,
        "auth": auth,
        "tier": body.get("tier", ""),
        "caps": body.get("caps", []),
    }
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
    if name not in smart_router.BACKENDS:
        raise HTTPException(404, f"backend '{name}' not found")
    del smart_router.BACKENDS[name]
    backend_enabled.pop(name, None)
    return {"ok": True, "message": f"backend '{name}' deleted"}


@router.post("/api/backends/{name}/toggle", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def admin_toggle_backend(name: str):
    _stats, _lock, backend_enabled = stats_context()
    if name not in smart_router.BACKENDS:
        raise HTTPException(404, f"backend '{name}' not found")
    current = backend_enabled.get(name, True)
    backend_enabled[name] = not current
    return {"ok": True, "enabled": not current}


@router.post("/api/backends/{name}/test", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def admin_test_backend(name: str):
    if name not in smart_router.BACKENDS:
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
                _log.debug("skip malformed fallback log line: %s", type(exc).__name__)
    return {
        "model": "Round 12 (Qwen3-1.7B)",
        "accuracy": "89.7%",
        "data_count": 3190,
        "fallback_log_count": log_count,
        "threshold": 100,
        "recent_fallbacks": recent_logs,
    }


@router.post("/api/retrain", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def admin_trigger_retrain():
    async with _RETRAIN_LOCK:
        for job in _RETRAIN_JOBS.values():
            if job.get("status") == "running":
                return {
                    "status": "already_running",
                    "job_id": job.get("job_id"),
                }
        job_id = f"retrain-{int(time.time())}"
        _RETRAIN_JOBS[job_id] = {
            "job_id": job_id,
            "status": "running",
            "started_at": time.time(),
            "output": "",
        }

    asyncio.create_task(_run_retrain_job(job_id))
    return {"status": "started", "job_id": job_id}


async def _run_retrain_job(job_id: str) -> None:
    try:
        result = await asyncio.to_thread(
            subprocess.run,
            [sys.executable, "auto_retrain.py", "--force"],
            capture_output=True,
            text=True,
            timeout=_RETRAIN_TIMEOUT_SEC,
            cwd=str(REPO_ROOT),
        )
        output = (result.stdout or result.stderr or "")[-500:]
        status = "completed" if result.returncode == 0 else "failed"
        _RETRAIN_JOBS[job_id] = {
            "job_id": job_id,
            "status": status,
            "returncode": result.returncode,
            "output": output,
            "finished_at": time.time(),
        }
    except subprocess.TimeoutExpired:
        _log.warning("admin retrain job timed out: %s", job_id)
        _RETRAIN_JOBS[job_id] = {
            "job_id": job_id,
            "status": "timeout",
            "output": "",
            "finished_at": time.time(),
        }
    except Exception as exc:
        _log.warning("admin retrain job failed: %s err=%s", job_id, type(exc).__name__)
        _RETRAIN_JOBS[job_id] = {
            "job_id": job_id,
            "status": "error",
            "output": "",
            "finished_at": time.time(),
        }
