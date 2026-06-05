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
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from routes.admin_auth import verify_admin, verify_csrf
from routes.admin_state import FALLBACK_LOG, stats_context
from routes.ops_metrics import _backend_call_detail

router = APIRouter()
REPO_ROOT = Path(__file__).resolve().parent.parent
_log = logging.getLogger(__name__)

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


# ── Backend health dashboard (M22) ───────────────────────────────────────


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
    cooled = sum(1 for b in backends if b["cooldown_remaining_s"] > 0)

    return {
        "backends": backends,
        "summary": {
            "total": len(backends),
            "healthy": healthy,
            "degraded": degraded,
            "dead": dead,
            "cooled": cooled,
        },
    }


# -- Fallback root cause analysis (M23) -----------------------------------


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

    # Aggregate by original_backend
    by_backend: dict[str, int] = {}
    for e in entries:
        orig = e.get("original_backend", "unknown")
        by_backend[orig] = by_backend.get(orig, 0) + 1

    by_backend_list = sorted(
        [{"backend": k, "count": v} for k, v in by_backend.items()],
        key=lambda x: -int(x["count"]),
    )[:10]

    # Aggregate by intent
    by_intent: dict[str, int] = {}
    for e in entries:
        intent = e.get("intent", "unknown")
        by_intent[intent] = by_intent.get(intent, 0) + 1

    by_intent_list = sorted(
        [{"intent": k, "count": v} for k, v in by_intent.items()],
        key=lambda x: -int(x["count"]),
    )[:10]

    # Hourly trend (last 24h)
    import collections
    hourly: dict[str, int] = collections.Counter()
    for e in entries:
        ts = e.get("timestamp", "")
        if len(ts) >= 13:
            hour = ts[:13]  # "2026-06-01 14"
            hourly[hour] += 1
    hourly_list = sorted([
        {"hour": k, "count": v} for k, v in hourly.items()
    ], key=lambda x: x["hour"])

    return {
        "total": len(entries),
        "by_backend": by_backend_list,
        "by_intent": by_intent_list,
        "hourly_trend": hourly_list[-24:],
    }


# -- Retrain job progress (M24c) ------------------------------------------


@router.get("/api/retrain/jobs", dependencies=[Depends(verify_admin)])
async def admin_retrain_jobs():
    """Return all retrain job statuses."""
    jobs = []
    for job_id, job in sorted(_RETRAIN_JOBS.items(), key=lambda x: -float(x[1].get("started_at", 0) or 0)):
        jobs.append({
            "job_id": job_id,
            "status": job.get("status", "unknown"),
            "started_at": job.get("started_at", 0),
            "finished_at": job.get("finished_at"),
            "output": job.get("output", ""),
            "returncode": job.get("returncode"),
        })
    return {"jobs": jobs}


# -- Key/URL inventory (M25) ----------------------------------------------


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
    from backends_registry import BACKENDS, DISABLED_HOST_DEPENDENT_BACKENDS
    import key_pool as kp

    backends = []
    for name in sorted(BACKENDS.keys()):
        cfg = BACKENDS[name]
        raw_key = cfg.get("key", "")
        backends.append({
            "name": name,
            "url": cfg.get("url", ""),
            "key_masked": _mask_key(raw_key),
            "key_configured": bool(raw_key and raw_key not in ("none", "")),
            "model": cfg.get("model", ""),
            "fmt": cfg.get("fmt", "openai"),
        })
    # Also list disabled backends
    for name in sorted(DISABLED_HOST_DEPENDENT_BACKENDS.keys()):
        if name not in BACKENDS:
            cfg = DISABLED_HOST_DEPENDENT_BACKENDS[name]
            raw_key = cfg.get("key", "")
            backends.append({
                "name": name,
                "url": cfg.get("url", ""),
                "key_masked": _mask_key(raw_key),
                "key_configured": bool(raw_key and raw_key not in ("none", "")),
                "model": cfg.get("model", ""),
                "fmt": cfg.get("fmt", "openai"),
            })

    pools = kp.pool_snapshot()
    return {"backends": backends, "key_pools": pools}


# -- Agent task management (M26) ------------------------------------------


# ── SSE log stream (Phase 1.2) ───────────────────────────────────────────
# A simple in-process pub-sub for log events.  Each SSE client gets an
# ``asyncio.Queue``.  When a new log entry arrives the dispatcher fans
# it out to every queue.

_log_subscribers: list[asyncio.Queue[dict | None]] = []
_log_subscribers_lock = asyncio.Lock()

# Stored main event-loop reference for SSE fan-out from non-async paths.
_main_sse_loop: asyncio.AbstractEventLoop | None = None


def _set_sse_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Called once at startup to capture the asyncio event loop."""
    global _main_sse_loop
    _main_sse_loop = loop


async def publish_log_event(event: dict) -> None:
    """Push *event* to every active SSE subscriber (fire-and-forget)."""
    async with _log_subscribers_lock:
        dead: list[int] = []
        for idx, q in enumerate(_log_subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                dead.append(idx)
        for idx in reversed(dead):
            _log_subscribers.pop(idx)


async def _log_sse_generator(
    queue: asyncio.Queue[dict | None],
) -> AsyncGenerator[str, None]:
    """Yield SSE-formatted strings for every log event in *queue*."""
    try:
        # Send a keepalive comment immediately so the connection is
        # established before we start waiting for events.
        yield ": connected\n\n"
        while True:
            event: dict | None = await queue.get()
            if event is None:
                # Sentinel: client should close
                break
            data = json.dumps(event, ensure_ascii=False)
            yield f"data: {data}\n\n"
    except asyncio.CancelledError:
        pass


@router.get("/api/logs/stream", dependencies=[Depends(verify_admin)])
async def admin_logs_stream():
    """SSE endpoint that streams log events in real time."""
    queue: asyncio.Queue[dict | None] = asyncio.Queue(maxsize=256)
    async with _log_subscribers_lock:
        _log_subscribers.append(queue)

    async def _cleanup():
        async with _log_subscribers_lock:
            if queue in _log_subscribers:
                _log_subscribers.remove(queue)

    async def _wrapped():
        try:
            async for chunk in _log_sse_generator(queue):
                yield chunk
        finally:
            await _cleanup()

    return StreamingResponse(
        _wrapped(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/api/agent-tasks", dependencies=[Depends(verify_admin)])
async def admin_agent_tasks(
    status: str = "",
    limit: int = 50,
    offset: int = 0,
):
    """List agent tasks with optional status filter and pagination."""
    try:
        from routes.agent_task_store import get_task_store

        store = get_task_store()
        all_tasks = list(store.values())
        if status:
            all_tasks = [t for t in all_tasks if t.get("status") == status]
        all_tasks.sort(key=lambda t: t.get("created_at", 0), reverse=True)
        total = len(all_tasks)
        page = all_tasks[offset : offset + limit]

        items = []
        for t in page:
            request = t.get("request", {})
            items.append({
                "task_id": request.get("task_id", ""),
                "status": t.get("status", "unknown"),
                "created_at": t.get("created_at", 0),
                "updated_at": t.get("updated_at", 0),
                "worker_id": request.get("worker_id", ""),
                "backend": request.get("backend", ""),
                "description": request.get("description", ""),
                "has_result": "result" in t,
            })
        return {"tasks": items, "total": total, "offset": offset, "limit": limit}
    except ImportError:
        return {"tasks": [], "total": 0, "offset": 0, "limit": limit}


@router.get("/api/agent-tasks/{task_id}", dependencies=[Depends(verify_admin)])
async def admin_agent_task_detail(task_id: str):
    """Get detailed information about a specific agent task."""
    try:
        from routes.agent_task_store import get_task_store

        store = get_task_store()
        if not store.contains(task_id):
            raise HTTPException(404, "Task not found")
        task = store.get(task_id)
        events = store.get_events(task_id)
        return {
            "task_id": task_id,
            "status": task.get("status", "unknown"),
            "created_at": task.get("created_at", 0),
            "updated_at": task.get("updated_at", 0),
            "request": task.get("request", {}),
            "result": task.get("result"),
            "events": events[-20:],
        }
    except ImportError:
        raise HTTPException(503, "Task store not available")


@router.post("/api/agent-tasks/{task_id}/cancel", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def admin_agent_task_cancel(task_id: str):
    """Cancel an agent task by setting cancel_requested flag."""
    try:
        from routes.agent_task_store import get_task_store

        store = get_task_store()
        if not store.contains(task_id):
            raise HTTPException(404, "Task not found")
        task = store.get(task_id)
        current_status = task.get("status", "")
        if current_status in ("completed", "failed", "cancelled"):
            raise HTTPException(409, f"Cannot cancel task in {current_status} status")
        request = dict(task.get("request", {}))
        request["cancel_requested"] = True
        task["request"] = request
        task["updated_at"] = time.time()
        store.update(task_id)
        store.append_event(task_id, {"type": "cancel_requested", "by": "admin"})
        return {"task_id": task_id, "status": "cancel_requested"}
    except ImportError:
        raise HTTPException(503, "Task store not available")


@router.post("/api/agent-tasks/{task_id}/retry", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def admin_agent_task_retry(task_id: str):
    """Retry a failed task by resetting its status to accepted."""
    try:
        from routes.agent_task_store import get_task_store

        store = get_task_store()
        if not store.contains(task_id):
            raise HTTPException(404, "Task not found")
        task = store.get(task_id)
        current_status = task.get("status", "")
        if current_status not in ("failed", "quarantined"):
            raise HTTPException(409, f"Cannot retry task in {current_status} status")
        task["status"] = "accepted"
        task["updated_at"] = time.time()
        if "result" in task:
            del task["result"]
        request = dict(task.get("request", {}))
        request["cancel_requested"] = False
        task["request"] = request
        store.update(task_id)
        store.append_event(task_id, {"type": "retry", "by": "admin"})
        return {"task_id": task_id, "status": "accepted"}
    except ImportError:
        raise HTTPException(503, "Task store not available")


# -- Config import/export (Phase 1.3) ------------------------------------

_CONFIG_EXPORT_VERSION = "1.0"
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_OVERLAY_PATH = _DATA_DIR / "backend_overrides.json"
_ADMIT_PATH = _DATA_DIR / "backend_admission.json"


@router.get("/api/config/export", dependencies=[Depends(verify_admin)])
async def admin_config_export():
    """Export backend overrides and admission config as a single JSON blob."""
    config: dict = {
        "version": _CONFIG_EXPORT_VERSION,
        "exported_at": time.time(),
        "backend_overrides": {},
        "backend_admission": {},
    }
    if _OVERLAY_PATH.exists():
        try:
            config["backend_overrides"] = json.loads(
                _OVERLAY_PATH.read_text(encoding="utf-8")
            )
        except (json.JSONDecodeError, OSError):
            pass
    if _ADMIT_PATH.exists():
        try:
            config["backend_admission"] = json.loads(
                _ADMIT_PATH.read_text(encoding="utf-8")
            )
        except (json.JSONDecodeError, OSError):
            pass
    return config


@router.post("/api/config/import", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def admin_config_import(body: dict):
    """Import backend overrides and admission config from a JSON payload.

    Accepts the same structure returned by ``/api/config/export``.
    Only the ``backend_overrides`` and ``backend_admission`` keys are
    imported; everything else is ignored.
    """
    version = body.get("version", "")
    if version != _CONFIG_EXPORT_VERSION:
        raise HTTPException(
            422,
            f"Unsupported config version: {version!r} (expected {_CONFIG_EXPORT_VERSION})",
        )
    imported: list[str] = []
    overrides = body.get("backend_overrides")
    if isinstance(overrides, dict):
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        _OVERLAY_PATH.write_text(
            json.dumps(overrides, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        imported.append("backend_overrides")
    admission = body.get("backend_admission")
    if isinstance(admission, dict):
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        _ADMIT_PATH.write_text(
            json.dumps(admission, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        imported.append("backend_admission")
    _log.info("admin: config imported sections=%s", imported)
    # Reload backends in-process so imported config takes effect immediately.
    try:
        from backends_registry import _load_backend_overlay
        _load_backend_overlay()
        _log.info("admin: backends reloaded after config import")
    except ImportError:
        _log.warning("admin: backends_registry not available, config requires restart")
    return {"ok": True, "imported": imported}


# -- Device gateway management (Phase 3.1) --------------------------------


@router.get("/api/devices", dependencies=[Depends(verify_admin)])
async def admin_devices():
    """List all connected devices from the device gateway session registry."""
    try:
        from device_gateway.sessions import registry

        sessions_info = []
        with registry._lock:
            for device_id, session in registry._sessions.items():
                sessions_info.append({
                    "device_id": device_id,
                    "fw_rev": session.fw_rev,
                    "capabilities": session.capabilities,
                    "last_uptime_ms": session.last_uptime_ms,
                    "inflight_count": len(session.inflight_tasks),
                })
        return {"devices": sessions_info, "total": len(sessions_info)}
    except (ImportError, AttributeError):
        return {"devices": [], "total": 0, "note": "Device gateway not available"}


@router.get("/api/devices/{device_id}", dependencies=[Depends(verify_admin)])
async def admin_device_detail(device_id: str):
    """Get detailed information about a specific device."""
    try:
        from device_gateway.sessions import registry

        session = registry.get(device_id)
        if session is None:
            raise HTTPException(404, "Device not connected")
        with session.inflight_lock:
            inflight = list(session.inflight_tasks.values())
        return {
            "device_id": device_id,
            "fw_rev": session.fw_rev,
            "capabilities": session.capabilities,
            "last_uptime_ms": session.last_uptime_ms,
            "inflight_tasks": inflight,
        }
    except HTTPException:
        raise
    except (ImportError, AttributeError):
        raise HTTPException(503, "Device gateway not available")


@router.post("/api/devices/{device_id}/restart", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def admin_device_restart(device_id: str):
    """Send a restart command to a connected device."""
    try:
        from device_gateway.sessions import registry
        from device_gateway.protocol import ack_frame

        session = registry.get(device_id)
        if session is None:
            raise HTTPException(404, "Device not connected")
        await session.send_json({"type": "restart", "device_id": device_id})
        return {"device_id": device_id, "command": "restart", "sent": True}
    except HTTPException:
        raise
    except (ImportError, AttributeError):
        raise HTTPException(503, "Device gateway not available")
    except Exception as exc:
        raise HTTPException(500, f"Failed to send restart: {exc}")


# -- Alert rules management (Phase 3.2) -----------------------------------

_ALERT_RULES_PATH = Path(__file__).resolve().parent.parent / "data" / "alert_rules.json"
_ALERT_RULES_LOCK = asyncio.Lock()

_ALLOWED_CONDITIONS = {"gt", "lt", "eq"}
_ALLOWED_METRICS = {"error_rate", "latency_ms", "fallback_rate", "request_count"}


def _read_alert_rules() -> list[dict]:
    if not _ALERT_RULES_PATH.exists():
        return []
    try:
        data = json.loads(_ALERT_RULES_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _write_alert_rules(rules: list[dict]) -> None:
    _ALERT_RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
    _ALERT_RULES_PATH.write_text(
        json.dumps(rules, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


@router.get("/api/alerts/rules", dependencies=[Depends(verify_admin)])
async def admin_alert_rules_list():
    """List all alert rules."""
    return {"rules": _read_alert_rules()}


@router.post("/api/alerts/rules", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def admin_alert_rules_create(body: dict):
    """Create a new alert rule."""
    # Validate fields
    condition = body.get("condition", "gt")
    if condition not in _ALLOWED_CONDITIONS:
        raise HTTPException(422, f"Invalid condition: {condition!r} (allowed: {_ALLOWED_CONDITIONS})")
    metric = body.get("metric", "error_rate")
    if metric not in _ALLOWED_METRICS:
        raise HTTPException(422, f"Invalid metric: {metric!r} (allowed: {_ALLOWED_METRICS})")
    threshold = body.get("threshold", 0.5)
    if not isinstance(threshold, (int, float)):
        raise HTTPException(422, f"threshold must be a number, got {type(threshold).__name__}")
    window_sec = body.get("window_sec", 300)
    if not isinstance(window_sec, (int, float)) or window_sec < 10:
        raise HTTPException(422, "window_sec must be >= 10")

    async with _ALERT_RULES_LOCK:
        rules = _read_alert_rules()
        rule_id = f"alert-{int(time.time())}-{len(rules)}"
        rule = {
            "rule_id": rule_id,
            "name": body.get("name", "Untitled"),
            "metric": metric,
            "condition": condition,
            "threshold": threshold,
            "window_sec": int(window_sec),
            "enabled": body.get("enabled", True),
            "notify": body.get("notify", []),
            "created_at": time.time(),
        }
        rules.append(rule)
        _write_alert_rules(rules)
    _log.info("admin: created alert rule %s", rule_id)
    return {"ok": True, "rule": rule}


@router.put("/api/alerts/rules/{rule_id}", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def admin_alert_rules_update(rule_id: str, body: dict):
    """Update an existing alert rule."""
    async with _ALERT_RULES_LOCK:
        rules = _read_alert_rules()
        for rule in rules:
            if rule.get("rule_id") == rule_id:
                for key in ("name", "metric", "condition", "threshold", "window_sec", "enabled", "notify"):
                    if key in body:
                        rule[key] = body[key]
                _write_alert_rules(rules)
                _log.info("admin: updated alert rule %s", rule_id)
                return {"ok": True, "rule": rule}
    raise HTTPException(404, f"Alert rule '{rule_id}' not found")


@router.delete("/api/alerts/rules/{rule_id}", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def admin_alert_rules_delete(rule_id: str):
    """Delete an alert rule."""
    async with _ALERT_RULES_LOCK:
        rules = _read_alert_rules()
        new_rules = [r for r in rules if r.get("rule_id") != rule_id]
        if len(new_rules) == len(rules):
            raise HTTPException(404, f"Alert rule '{rule_id}' not found")
        _write_alert_rules(new_rules)
    _log.info("admin: deleted alert rule %s", rule_id)
    return {"ok": True, "deleted": rule_id}
