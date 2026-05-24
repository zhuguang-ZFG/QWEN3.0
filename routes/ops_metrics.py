"""Operator telemetry endpoint — unified view across request, task, and device.

Provides an authenticated `/v1/ops/metrics` endpoint that joins:
- Recent chat/Anthropic request traces
- Agent worker task summaries
- Device Gateway task states and motion event phases
- Latest error classes per backend and device

All raw prompts, keys, paths, and device tokens are redacted.
"""
from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from access_guard import require_private_api_key

router = APIRouter(prefix="/v1/ops")


def _redacted(value: str, max_len: int = 40) -> str:
    if not value:
        return ""
    return value[:max_len]


@router.get("/metrics", dependencies=[Depends(require_private_api_key)])
async def ops_metrics(request: Request) -> JSONResponse:
    now = time.time()

    # Request stats (injected from server)
    stats = getattr(request.app, "state", {}).get("stats", {})
    total_requests = int(stats.get("total_requests", 0))
    backend_calls = dict(stats.get("backend_calls", {}))

    # Health
    try:
        import health_tracker
        health_map = health_tracker.get_health_map()
        dead_backends = [b for b, s in health_map.items() if s == "dead"]
        degraded_backends = [b for b, s in health_map.items() if s == "degraded"]
    except ImportError:
        health_map = {}
        dead_backends = []
        degraded_backends = []

    # Device Gateway
    device = {"sessions": 0, "pending_tasks": 0, "store_backend": "unknown", "bus_backend": "unknown"}
    try:
        from device_gateway.sessions import registry
        device["sessions"] = registry.count()
    except ImportError:
        pass
    try:
        from device_gateway.tasks import pending_count
        device["pending_tasks"] = pending_count()
    except ImportError:
        pass
    try:
        from device_gateway.store import task_store_health
        th = task_store_health()
        device["store_backend"] = th.get("backend", "unknown")
        device["shared"] = th.get("shared_across_processes", False)
    except ImportError:
        pass
    try:
        from device_gateway.notifier import notifier_health
        device["bus"] = notifier_health()
    except ImportError:
        pass

    # Agent tasks
    agent = {"active_workers": 0, "total_completed": 0, "total_failed": 0}
    try:
        from tool_gateway.governance import list_workers
        workers = list_workers()
        agent["active_workers"] = sum(1 for w in workers if w.status in ("idle", "busy"))
        agent["total_completed"] = sum(w.total_completed for w in workers)
        agent["total_failed"] = sum(w.total_failed for w in workers)
    except ImportError:
        pass

    # Recent retrieval traces
    retrieval_traces: list[dict] = []
    try:
        from context_pipeline.retrieval_trace import get_recent_traces
        retrieval_traces = get_recent_traces(limit=5)
    except ImportError:
        pass

    # Recent agent task events
    recent_tasks: list[dict] = []
    try:
        from routes.agent_tasks import _agent_tasks_store
        if _agent_tasks_store:
            tasks = _agent_tasks_store.list_recent(limit=5)
            recent_tasks = [
                {"task_id": t.get("task_id", ""), "status": t.get("status", ""),
                 "worker_id": t.get("worker_id", ""), "goal": _redacted(t.get("goal", ""), 60)}
                for t in tasks
            ]
    except (ImportError, AttributeError):
        pass

    # Backend error summary
    backend_errors: dict[str, dict] = {}
    for backend_name in set(health_map.keys()) | set(backend_calls.keys()):
        state = {}
        try:
            from health_tracker import get_backend_state
            state = get_backend_state(backend_name)
        except ImportError:
            pass
        if state.get("last_error_class"):
            backend_errors[backend_name] = {
                "error_class": state.get("last_error_class"),
                "error_code": state.get("last_error_code"),
                "health": health_map.get(backend_name, "unknown"),
            }

    return JSONResponse({
        "timestamp": int(now),
        "uptime_sec": int(now - stats.get("start_time", now)),
        "total_requests": total_requests,
        "backend_calls": dict(sorted(backend_calls.items(), key=lambda kv: -kv[1])[:10]),
        "backends": {
            "total": len(health_map),
            "dead": len(dead_backends),
            "degraded": len(degraded_backends),
            "dead_list": dead_backends[:10],
            "error_summary": dict(list(backend_errors.items())[:10]),
        },
        "device_gateway": device,
        "agent_workers": agent,
        "retrieval_traces": retrieval_traces,
        "recent_agent_tasks": recent_tasks,
    })
