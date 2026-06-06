"""Admin JSON API routes — core stats, health, retrain, key inventory.

Sub-modules (extracted for size):
  - routes.admin_sse         → SSE log stream
  - routes.admin_agent_tasks → Agent task CRUD
  - routes.admin_devices     → Device gateway management
  - routes.admin_alerts      → Alert rules CRUD
  - routes.admin_config      → Config import/export
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from routes.admin_agent_tasks import router as _agent_tasks_router
from routes.admin_alerts import _ALERT_RULES_PATH
from routes.admin_alerts import router as _alerts_router
from routes.admin_auth import verify_admin, verify_csrf
from routes.admin_config import (
    _ADMIT_PATH,
    _DATA_DIR,
    _OVERLAY_PATH,
)
from routes.admin_config import router as _config_router
from routes.admin_devices import router as _devices_router

# ── Backward-compatible re-exports ─────────────────────────────────────────
from routes.admin_sse import (
    _log_sse_generator,
    _log_subscribers,
    _main_sse_loop,
    _set_sse_event_loop,
    publish_log_event,
)

# ── Sub-module routers (include into main router) ──────────────────────────
from routes.admin_sse import router as _sse_router
from routes.admin_state import FALLBACK_LOG, stats_context
from routes.ops_metrics import _backend_call_detail

router = APIRouter()
REPO_ROOT = Path(__file__).resolve().parent.parent
_log = logging.getLogger(__name__)

# Include sub-module routes
router.include_router(_sse_router)
router.include_router(_agent_tasks_router)
router.include_router(_devices_router)
router.include_router(_alerts_router)
router.include_router(_config_router)

_RETRAIN_LOCK = asyncio.Lock()
_RETRAIN_JOBS: dict[str, dict[str, object]] = {}


def _env_int(name: str, default: int) -> int:
    """Safe int-from-env that never crashes on empty/malformed values."""
    val = os.environ.get(name, "")
    if not val:
        return default
    try:
        return int(val)
    except ValueError:
        return default


_RETRAIN_TIMEOUT_SEC = _env_int("LIMA_RETRAIN_TIMEOUT_SEC", 600)

_VERSION_CACHE: dict[str, str] = {}


def _get_version_info() -> dict[str, str]:
    """Return git commit short hash + python version, cached after first call."""
    if _VERSION_CACHE:
        return dict(_VERSION_CACHE)
    commit = "unknown"
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(REPO_ROOT),
        )
        if result.returncode == 0:
            commit = result.stdout.strip()
    except Exception as exc:
        _log.debug("git commit extraction failed: %s", type(exc).__name__)
    _VERSION_CACHE["git_commit"] = commit
    _VERSION_CACHE["python_version"] = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    return dict(_VERSION_CACHE)


@router.get("/api/stats", dependencies=[Depends(verify_admin)])
async def admin_stats():
    stats, lock, _enabled = stats_context()
    with lock:
        uptime = int(time.time() - stats["start_time"])
        total = stats["total_requests"]
        backend_calls = {
            name: _backend_call_detail(value)
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
            "version": _get_version_info(),
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


@router.get("/api/context-injection-traces", dependencies=[Depends(verify_admin)])
async def admin_context_injection_traces():
    try:
        from context_injection_trace import get_recent_traces
        return get_recent_traces(limit=20)
    except ImportError:
        return []


@router.get("/api/coding-pool-admission", dependencies=[Depends(verify_admin)])
async def admin_coding_pool_admission():
    try:
        from coding_pool_admission import summarize_admission
        return summarize_admission()
    except ImportError:
        return {}


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
                return {"status": "already_running", "job_id": job.get("job_id")}
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
            "job_id": job_id, "status": status, "returncode": result.returncode,
            "output": output, "finished_at": time.time(),
        }
    except subprocess.TimeoutExpired:
        _log.warning("admin retrain job timed out: %s", job_id)
        _RETRAIN_JOBS[job_id] = {"job_id": job_id, "status": "timeout", "output": "", "finished_at": time.time()}
    except Exception as exc:
        _log.warning("admin retrain job failed: %s err=%s", job_id, type(exc).__name__)
        _RETRAIN_JOBS[job_id] = {"job_id": job_id, "status": "error", "output": "", "finished_at": time.time()}


@router.get("/api/backend-health", dependencies=[Depends(verify_admin)])
async def admin_backend_health():
    """Aggregate health_tracker + circuit_breaker data for all backends."""
    try:
        import health_tracker
        import router_circuit_breaker as cb_mod
        from backends_registry import BACKENDS

        scores = health_tracker.get_scores()
        health_map = health_tracker.get_health_map()
        latency_map = health_tracker.get_latency_map()
        cb_data = cb_mod.cb_status()
    except ImportError:
        return {"backends": [], "summary": {}}

    backends = []
    for name in sorted(BACKENDS.keys()):
        state = health_tracker.get_backend_state(name)
        cb_info = cb_data.get(name, {})
        backends.append({
            "name": name,
            "health": health_map.get(name, "unknown"),
            "score": round(scores.get(name, 50.0), 1),
            "avg_latency_ms": round(latency_map.get(name, 0), 1),
            "consecutive_failures": state.get("consecutive_failures", 0),
            "cooldown_remaining_s": round(state.get("cooldown_remaining_s", 0), 1),
            "last_error_code": state.get("last_error_code"),
            "cb_state": cb_info.get("state", "closed"),
            "cb_failures": cb_info.get("failures", 0),
            "cb_total_calls": cb_info.get("total_calls", 0),
            "cb_error_rate": cb_info.get("error_rate", "0.0%"),
        })

    healthy = sum(1 for b in backends if b["health"] == "healthy")
    degraded = sum(1 for b in backends if b["health"] == "degraded")
    dead = sum(1 for b in backends if b["health"] == "dead")
    unknown = sum(1 for b in backends if b["health"] == "unknown")
    cooled = sum(1 for b in backends if b["cooldown_remaining_s"] > 0)
    probed = len(backends) - unknown
    cb_tracked = sum(1 for b in backends if b["cb_total_calls"] > 0)

    return {
        "backends": backends,
        "summary": {
            "total": len(backends), "healthy": healthy, "degraded": degraded,
            "dead": dead, "unknown": unknown, "probed": probed,
            "cooled": cooled, "cb_tracked": cb_tracked,
        },
    }


@router.get("/api/fallback-analysis", dependencies=[Depends(verify_admin)])
async def admin_fallback_analysis():
    """Parse fallback_log.jsonl and aggregate by original_backend."""
    entries = []
    try:
        with open(FALLBACK_LOG, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    except FileNotFoundError:
        pass

    by_backend: dict[str, int] = {}
    for e in entries:
        orig = e.get("original_backend", "unknown")
        by_backend[orig] = by_backend.get(orig, 0) + 1
    by_backend_list = sorted(
        [{"backend": k, "count": v} for k, v in by_backend.items()],
        key=lambda x: -int(x["count"]),
    )[:10]

    by_intent: dict[str, int] = {}
    for e in entries:
        intent = e.get("intent", "unknown")
        by_intent[intent] = by_intent.get(intent, 0) + 1
    by_intent_list = sorted(
        [{"intent": k, "count": v} for k, v in by_intent.items()],
        key=lambda x: -int(x["count"]),
    )[:10]

    import collections
    hourly: dict[str, int] = collections.Counter()
    for e in entries:
        ts = e.get("timestamp", "")
        if len(ts) >= 13:
            hourly[ts[:13]] += 1
    hourly_list = sorted([{"hour": k, "count": v} for k, v in hourly.items()], key=lambda x: x["hour"])

    return {
        "total": len(entries),
        "by_backend": by_backend_list,
        "by_intent": by_intent_list,
        "hourly_trend": hourly_list[-24:],
    }


@router.get("/api/retrain/jobs", dependencies=[Depends(verify_admin)])
async def admin_retrain_jobs():
    """Return all retrain job statuses."""
    jobs = []
    for job_id, job in sorted(_RETRAIN_JOBS.items(), key=lambda x: -float(x[1].get("started_at", 0) or 0)):
        jobs.append({
            "job_id": job_id, "status": job.get("status", "unknown"),
            "started_at": job.get("started_at", 0), "finished_at": job.get("finished_at"),
            "output": job.get("output", ""), "returncode": job.get("returncode"),
        })
    return {"jobs": jobs}


def _mask_key(raw: str) -> str:
    """Mask API key: show first 4 + last 4 chars."""
    if not raw or raw in ("none", ""):
        return ""
    if len(raw) <= 8:
        return raw[:2] + "*" * (len(raw) - 2)
    return raw[:4] + "*" * (len(raw) - 8) + raw[-4:]


@router.get("/api/key-url-inventory", dependencies=[Depends(verify_admin)])
async def admin_key_url_inventory():
    """List all backends with masked keys and URLs."""
    import key_pool as kp
    from backends_registry import BACKENDS, DISABLED_HOST_DEPENDENT_BACKENDS

    backends = []
    for name in sorted(BACKENDS.keys()):
        cfg = BACKENDS[name]
        raw_key = cfg.get("key", "")
        backends.append({
            "name": name, "url": cfg.get("url", ""), "key_masked": _mask_key(raw_key),
            "key_configured": bool(raw_key and raw_key not in ("none", "")),
            "model": cfg.get("model", ""), "fmt": cfg.get("fmt", "openai"),
        })
    for name in sorted(DISABLED_HOST_DEPENDENT_BACKENDS.keys()):
        if name not in BACKENDS:
            cfg = DISABLED_HOST_DEPENDENT_BACKENDS[name]
            raw_key = cfg.get("key", "")
            backends.append({
                "name": name, "url": cfg.get("url", ""), "key_masked": _mask_key(raw_key),
                "key_configured": bool(raw_key and raw_key not in ("none", "")),
                "model": cfg.get("model", ""), "fmt": cfg.get("fmt", "openai"),
            })
    pools = kp.pool_snapshot()
    return {"backends": backends, "key_pools": pools}
