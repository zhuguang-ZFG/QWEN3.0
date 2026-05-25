"""Operator telemetry endpoint — unified view across request, task, and device.

Provides authenticated endpoints:
- `/v1/ops/metrics` — snapshot across all subsystems
- `/v1/ops/correlate?id=X` — cross-system trace by request/task/device id
- `/v1/ops/correlate/summary` — recent correlation overview

All raw prompts, keys, paths, and device tokens are redacted.
"""
from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from access_guard import require_private_api_key

router = APIRouter(prefix="/v1/ops")


def _redacted(value: str, max_len: int = 40) -> str:
    if not value:
        return ""
    return value[:max_len]


def _app_stats(request: Request) -> dict[str, Any]:
    state = getattr(request.app, "state", None)
    stats = getattr(state, "stats", {}) if state is not None else {}
    return stats if isinstance(stats, dict) else {}


def _backend_call_count(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int | float):
        return int(value)
    if isinstance(value, dict):
        count = value.get("count", 0)
        return int(count) if isinstance(count, int | float) else 0
    return 0


def _backend_call_detail(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return {
            "count": _backend_call_count(value),
            "success": int(value.get("success", 0)) if isinstance(value.get("success", 0), int | float) else 0,
            "total_ms": int(value.get("total_ms", 0)) if isinstance(value.get("total_ms", 0), int | float) else 0,
        }
    return {"count": _backend_call_count(value), "success": 0, "total_ms": 0}


def _top_backend_counts(backend_calls: dict[str, Any], limit: int = 10) -> dict[str, int]:
    ranked = sorted(
        ((name, _backend_call_count(value)) for name, value in backend_calls.items()),
        key=lambda item: -item[1],
    )
    return dict(ranked[:limit])


def _top_backend_details(backend_calls: dict[str, Any], limit: int = 10) -> dict[str, dict[str, Any]]:
    ranked_names = list(_top_backend_counts(backend_calls, limit=limit).keys())
    return {name: _backend_call_detail(backend_calls[name]) for name in ranked_names}


def _recent_agent_tasks(limit: int = 5) -> list[dict[str, Any]]:
    """Return recent agent tasks from the SQLite-backed store."""
    try:
        from routes.agent_tasks import _store
    except ImportError:
        return []

    try:
        tasks = sorted(
            _store.values(),
            key=lambda item: item.get("created_at", 0),
            reverse=True,
        )[:limit]
    except (AttributeError, TypeError):
        return []

    recent: list[dict[str, Any]] = []
    for task in tasks:
        request = task.get("request") if isinstance(task.get("request"), dict) else {}
        recent.append({
            "task_id": str(request.get("task_id", "")),
            "status": str(task.get("status", "")),
            "worker_id": str(task.get("worker_id", "")),
            "goal": _redacted(str(request.get("goal", "")), 60),
        })
    return recent


@router.get("/metrics", dependencies=[Depends(require_private_api_key)])
async def ops_metrics(request: Request) -> JSONResponse:
    now = time.time()

    # Request stats (injected from server)
    stats = _app_stats(request)
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

    recent_tasks = _recent_agent_tasks(limit=5)

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

    # ── Learning loop stats (PROD-008) ──────────────────────────────────────
    learning: dict[str, Any] = {}
    try:
        from session_memory.prompt_recall import recall_stats
        learning["prompt_recall"] = recall_stats()
    except ImportError:
        pass
    try:
        from context_pipeline.routing_weights import get_routing_weights
        rw = get_routing_weights()
        weights_data = rw._weights
        scenarios = sorted(set(w.scenario for w in weights_data.values()))
        learning["routing_weights"] = {
            "total_patterns": len(weights_data),
            "active_backends": len(set(w.backend for w in weights_data.values())),
            "top_scenarios": scenarios[:10],
        }
    except ImportError:
        pass
    try:
        from session_memory.eval_gate import revision_check
        revision = revision_check()
        learning["eval_gate"] = {
            "total_candidates": revision["total"],
            "promotable": sum(1 for c in revision.get("promotable", []) if c.get("can_promote")),
            "needs_approval": len(revision.get("needs_approval", [])),
            "blocked_by_rate": len(revision.get("blocked_by_pass_rate", [])),
        }
        promoted = [c for c in revision.get("promotable", []) if c.get("promoted")]
        learning["eval_gate"]["promoted_active"] = len(promoted)
    except ImportError:
        pass

    return JSONResponse({
        "timestamp": int(now),
        "uptime_sec": int(now - stats.get("start_time", now)),
        "total_requests": total_requests,
        "backend_calls": _top_backend_counts(backend_calls),
        "backend_call_details": _top_backend_details(backend_calls),
        "backends": {
            "total": len(health_map),
            "dead": len(dead_backends),
            "degraded": len(degraded_backends),
            "dead_list": dead_backends[:10],
            "error_summary": dict(list(backend_errors.items())[:10]),
        },
        "device_gateway": device,
        "agent_workers": agent,
        "learning": learning,
        "retrieval_traces": retrieval_traces,
        "recent_agent_tasks": recent_tasks,
    })


@router.get("/correlate/summary", dependencies=[Depends(require_private_api_key)])
async def ops_correlate_summary() -> JSONResponse:
    try:
        from observability.correlation import correlation_summary
        return JSONResponse(correlation_summary())
    except ImportError:
        return JSONResponse({"error": "correlation module not loaded"}, status_code=503)


@router.get("/correlate", dependencies=[Depends(require_private_api_key)])
async def ops_correlate(
    id: str = Query(default=""),
    request_id: str = Query(default=""),
    task_id: str = Query(default=""),
    device_id: str = Query(default=""),
) -> JSONResponse:
    target = id or request_id or task_id or device_id
    if not target:
        return JSONResponse(
            {"error": "Provide one of: request_id, task_id, or device_id"},
            status_code=400,
        )
    try:
        from observability.correlation import correlate_by_id, correlate_recent
        matched = correlate_by_id(target)
        if not matched:
            recent = correlate_recent(10)
            return JSONResponse({
                "target": target,
                "matched": [],
                "hint": "no events found for this id",
                "recent_events": recent,
            })
        # Build a trace timeline with cross-references
        trace: list[dict] = []
        seen_ids: set[str] = set()
        for event in matched:
            trace.append(event)
            for key in ("request_id", "task_id", "device_id"):
                eid = event.get(key, "")
                if eid and eid != target and eid not in seen_ids:
                    seen_ids.add(eid)
        # Pull in related events for discovered ids
        for related_id in list(seen_ids)[:5]:
            for event in correlate_by_id(related_id, limit=10):
                if event not in trace:
                    trace.append(event)
        trace.sort(key=lambda e: e.get("ts", 0))
        return JSONResponse({
            "target": target,
            "matched_count": len(matched),
            "related_ids": sorted(seen_ids),
            "trace": trace,
        })
    except ImportError:
        return JSONResponse({"error": "correlation module not loaded"}, status_code=503)


@router.get("/eval/revision", dependencies=[Depends(require_private_api_key)])
async def ops_eval_revision() -> JSONResponse:
    """Return all eval candidates with promotion status."""
    try:
        from session_memory.eval_gate import revision_check
        return JSONResponse(revision_check())
    except ImportError:
        return JSONResponse({"error": "eval_gate module not loaded"}, status_code=503)


@router.post("/eval/approve", dependencies=[Depends(require_private_api_key)])
async def ops_eval_approve(request: Request) -> JSONResponse:
    """Manually approve a pattern candidate. Body: {pattern_key, rollback_notes}."""
    try:
        body = await request.json()
        pattern_key = body.get("pattern_key", "")
        rollback = body.get("rollback_notes", "")
        if not pattern_key:
            return JSONResponse({"error": "pattern_key required"}, status_code=400)
        from session_memory.eval_gate import approve_candidate
        return JSONResponse(approve_candidate(pattern_key, rollback))
    except ImportError:
        return JSONResponse({"error": "eval_gate module not loaded"}, status_code=503)


@router.post("/eval/apply", dependencies=[Depends(require_private_api_key)])
async def ops_eval_apply(request: Request) -> JSONResponse:
    """Apply an approved pattern to runtime routing weights. Body: {pattern_key}."""
    try:
        try:
            body = await request.json()
        except ValueError:
            return JSONResponse({"error": "valid JSON body required"}, status_code=400)
        if not isinstance(body, dict):
            return JSONResponse({"error": "JSON object body required"}, status_code=400)
        pattern_key = body.get("pattern_key", "")
        if not isinstance(pattern_key, str) or not pattern_key.strip():
            return JSONResponse({"error": "pattern_key required"}, status_code=400)
        from session_memory.eval_gate import apply_promotion
        return JSONResponse(apply_promotion(pattern_key))
    except ImportError:
        return JSONResponse({"error": "eval_gate module not loaded"}, status_code=503)
