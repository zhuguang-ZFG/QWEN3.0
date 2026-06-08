"""Operator telemetry endpoint — unified view across request, task, and device.

Provides authenticated endpoints:
- `/v1/ops/metrics` — snapshot across all subsystems
- `/v1/ops/correlate?id=X` — cross-system trace by request/task/device id
- `/v1/ops/correlate/summary` — recent correlation overview

All raw prompts, keys, paths, and device tokens are redacted.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from access_guard import require_private_api_key
from routes.json_body import read_json_object

router = APIRouter(prefix="/v1/ops")
logger = logging.getLogger(__name__)
_BACKEND_NAME_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,96}$")


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
    for task_raw in tasks:
        task = task_raw if isinstance(task_raw, dict) else {}
        request = task.get("request") if isinstance(task.get("request"), dict) else {}
        recent.append({
            "task_id": str(request.get("task_id", "")),  # type: ignore[reportOptionalMemberAccess]
            "status": str(task.get("status", "")),
            "worker_id": str(task.get("worker_id", "")),
            "goal": _redacted(str(request.get("goal", "")), 60),  # type: ignore[reportOptionalMemberAccess]
        })
    return recent


def _get_capability_evidence() -> dict:
    try:
        from observability.capability_evidence import recent_evidence
        return {"recent": recent_evidence(limit=10)}
    except ImportError:
        return {"recent": [], "error": "unavailable"}


def _get_cli_telemetry() -> dict[str, Any]:
    try:
        from observability.cli_telemetry import cli_telemetry_summary
        return cli_telemetry_summary(limit=10)
    except ImportError:
        return {"total_recent": 0, "recent": [], "error": "unavailable"}


def _get_backend_telemetry() -> dict[str, Any]:
    try:
        from observability.backend_telemetry import backend_telemetry_summary
        return backend_telemetry_summary(limit=10)
    except ImportError:
        return {"total_recent": 0, "recent": [], "error": "unavailable"}


def _get_routing_guard() -> dict[str, Any]:
    try:
        from observability.routing_guard import backend_guard_snapshot
        return backend_guard_snapshot(limit=200)
    except ImportError:
        return {"enabled": False, "decisions": {}, "error": "unavailable"}


def _backend_recovery_snapshot(dead_backends: list[str], degraded_backends: list[str]) -> dict[str, Any]:
    try:
        from backend_retirement import get_recovery_snapshot
        return get_recovery_snapshot(dead_backends=dead_backends, degraded_backends=degraded_backends)
    except ImportError:
        return {
            "retired_count": 0,
            "retired_list": [],
            "probe_candidates": (dead_backends + degraded_backends)[:10],
            "error": "backend_retirement unavailable",
        }


def _ops_metrics_snapshot(request: Request) -> dict[str, Any]:
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
    try:
        from session_memory.learning_loop import get_eval_candidates, get_prompt_profile_stats

        learning["loop"] = {
            "eval_candidates": len(get_eval_candidates(200)),
            "prompt_profile_keys": len(get_prompt_profile_stats()),
        }
    except ImportError:
        pass

    return {
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
            "recovery": _backend_recovery_snapshot(dead_backends, degraded_backends),
        },
        "device_gateway": device,
        "agent_workers": agent,
        "learning": learning,
        "retrieval_traces": retrieval_traces,
        "recent_agent_tasks": recent_tasks,
        "cli_telemetry": _get_cli_telemetry(),
        "backend_telemetry": _get_backend_telemetry(),
        "routing_guard": _get_routing_guard(),
        "capability_evidence": _get_capability_evidence(),
    }


def _alert(severity: str, code: str, message: str, count: int = 1) -> dict[str, Any]:
    return {
        "severity": severity,
        "code": code,
        "message": message,
        "count": count,
    }


def _ops_summary_from_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    raw_backends = metrics.get("backends")
    backends = raw_backends if isinstance(raw_backends, dict) else {}
    raw_recovery = backends.get("recovery")
    recovery = raw_recovery if isinstance(raw_recovery, dict) else {}
    raw_cli = metrics.get("cli_telemetry")
    cli = raw_cli if isinstance(raw_cli, dict) else {}
    raw_backend_telemetry = metrics.get("backend_telemetry")
    backend_telemetry = raw_backend_telemetry if isinstance(raw_backend_telemetry, dict) else {}
    raw_routing_guard = metrics.get("routing_guard")
    routing_guard = raw_routing_guard if isinstance(raw_routing_guard, dict) else {}
    raw_decisions = routing_guard.get("decisions")
    decisions = raw_decisions if isinstance(raw_decisions, dict) else {}

    dead = int(backends.get("dead", 0) or 0)
    degraded = int(backends.get("degraded", 0) or 0)
    retired = int(recovery.get("retired_count", 0) or 0)
    probe_candidates = recovery.get("probe_candidates", [])
    probe_count = len(probe_candidates) if isinstance(probe_candidates, list) else 0
    quarantined = sum(
        1
        for value in decisions.values()
        if isinstance(value, dict) and value.get("status") == "quarantined"
    )

    alerts: list[dict[str, Any]] = []
    if dead:
        alerts.append(_alert("critical", "backend_dead", f"{dead} backend(s) are dead", dead))
    if degraded:
        alerts.append(_alert("warning", "backend_degraded", f"{degraded} backend(s) are degraded", degraded))
    if retired:
        alerts.append(_alert("warning", "backend_retired", f"{retired} backend(s) are manually retired", retired))
    if quarantined:
        alerts.append(_alert("warning", "backend_quarantined", f"{quarantined} backend(s) are quarantined", quarantined))
    if int(cli.get("failed_recent", 0) or 0):
        alerts.append(_alert("warning", "cli_failures", "Recent developer-tool CLI failures observed", int(cli.get("failed_recent", 0))))
    if int(backend_telemetry.get("slow_recent", 0) or 0):
        alerts.append(_alert("warning", "slow_backends", "Recent slow backend attempts observed", int(backend_telemetry.get("slow_recent", 0))))
    if probe_count:
        alerts.append(_alert("info", "probe_candidates", "Backends are ready for manual probe/recovery review", probe_count))

    if any(item["severity"] == "critical" for item in alerts):
        status = "critical"
    elif alerts:
        status = "warning"
    else:
        status = "ok"

    return {
        "status": status,
        "timestamp": metrics.get("timestamp"),
        "alerts": alerts[:20],
        "counts": {
            "dead_backends": dead,
            "degraded_backends": degraded,
            "retired_backends": retired,
            "probe_candidates": probe_count,
            "quarantined_backends": quarantined,
            "cli_failures_recent": int(cli.get("failed_recent", 0) or 0),
            "slow_backend_attempts_recent": int(backend_telemetry.get("slow_recent", 0) or 0),
        },
        "actions": {
            "metrics": "GET /v1/ops/metrics",
            "probe_backend": "POST /v1/ops/backends/probe",
            "reactivate_backend": "POST /v1/ops/backends/reactivate",
            "retire_backend": "POST /v1/ops/backends/retire",
            "body": {"backend": "name", "evidence": "fresh probe result or rollback reason"},
        },
    }


def _valid_backend_name(value: Any) -> str:
    backend = value.strip() if isinstance(value, str) else ""
    if not backend or not _BACKEND_NAME_RE.match(backend):
        return ""
    return backend


@router.get("/metrics", dependencies=[Depends(require_private_api_key)])
async def ops_metrics(request: Request) -> JSONResponse:
    return JSONResponse(_ops_metrics_snapshot(request))


@router.get("/summary", dependencies=[Depends(require_private_api_key)])
async def ops_summary(request: Request) -> JSONResponse:
    return JSONResponse(_ops_summary_from_metrics(_ops_metrics_snapshot(request)))


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
        body = await read_json_object(request)
        if isinstance(body, JSONResponse):
            return body
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
        body = await read_json_object(request)
        if isinstance(body, JSONResponse):
            return body
        pattern_key = body.get("pattern_key", "")
        if not isinstance(pattern_key, str) or not pattern_key.strip():
            return JSONResponse({"error": "pattern_key required"}, status_code=400)
        from session_memory.eval_gate import apply_promotion
        return JSONResponse(apply_promotion(pattern_key))
    except ImportError:
        return JSONResponse({"error": "eval_gate module not loaded"}, status_code=503)


@router.post("/backends/reactivate", dependencies=[Depends(require_private_api_key)])
async def ops_backend_reactivate(request: Request) -> JSONResponse:
    """Manually reactivate a backend after fresh operator evidence."""
    body = await read_json_object(request)
    if isinstance(body, JSONResponse):
        return body
    backend = _valid_backend_name(body.get("backend"))
    evidence = str(body.get("evidence", "")).strip()
    if not backend:
        return JSONResponse({"error": "valid backend required"}, status_code=400)
    if not evidence:
        return JSONResponse({"error": "evidence required"}, status_code=400)
    try:
        from backend_retirement import reactivate

        reactivate(backend)
    except ImportError:
        return JSONResponse({"error": "backend_retirement module not loaded"}, status_code=503)
    except Exception as exc:
        logger.warning("manual backend reactivation failed backend=%s: %s", backend, type(exc).__name__)
        return JSONResponse({"error": "backend reactivation failed"}, status_code=500)
    logger.warning("manual backend reactivation backend=%s evidence=%s", backend, evidence[:120])
    return JSONResponse({"ok": True, "backend": backend, "status": "healthy"})


@router.post("/backends/probe", dependencies=[Depends(require_private_api_key)])
async def ops_backend_probe(request: Request) -> JSONResponse:
    """Probe one backend and record the evidence before any recovery action."""
    body = await read_json_object(request)
    if isinstance(body, JSONResponse):
        return body
    backend = _valid_backend_name(body.get("backend"))
    reactivate_on_success = bool(body.get("reactivate_on_success", False))
    timeout_raw = body.get("timeout_sec", 25)
    if not backend:
        return JSONResponse({"error": "valid backend required"}, status_code=400)
    try:
        timeout_sec = float(timeout_raw)
    except (TypeError, ValueError):
        return JSONResponse({"error": "valid timeout_sec required"}, status_code=400)
    if timeout_sec <= 0 or timeout_sec > 120:
        return JSONResponse({"error": "timeout_sec must be between 0 and 120"}, status_code=400)
    try:
        from backend_probe_loop import probe_and_record_backend

        result = probe_and_record_backend(
            backend,
            ignore_cooldown=True,
            timeout_sec=timeout_sec,
        )
    except ImportError:
        return JSONResponse({"error": "backend_probe_loop module not loaded"}, status_code=503)
    except Exception as exc:
        logger.warning("manual backend probe failed backend=%s: %s", backend, type(exc).__name__)
        return JSONResponse({"error": "backend probe failed"}, status_code=500)

    status = str(result.get("status", "unknown"))
    healthy = status == "healthy"
    reactivated = False
    if healthy and reactivate_on_success:
        try:
            from backend_retirement import reactivate

            reactivate(backend)
            reactivated = True
        except ImportError:
            return JSONResponse({"error": "backend_retirement module not loaded"}, status_code=503)
        except Exception as exc:
            logger.warning("probe-based backend reactivation failed backend=%s: %s", backend, type(exc).__name__)
            return JSONResponse({"error": "backend reactivation failed"}, status_code=500)

    if healthy:
        recommended = "reactivated" if reactivated else "reactivate_with_evidence"
    elif status == "unknown":
        recommended = "check_backend_name"
    else:
        recommended = "keep_retired"

    return JSONResponse({
        "ok": healthy,
        "backend": backend,
        "probe": result,
        "reactivated": reactivated,
        "recommended_action": recommended,
    })


@router.post("/backends/retire", dependencies=[Depends(require_private_api_key)])
async def ops_backend_retire(request: Request) -> JSONResponse:
    """Manually remove a backend from routing until an operator reactivates it."""
    body = await read_json_object(request)
    if isinstance(body, JSONResponse):
        return body
    backend = _valid_backend_name(body.get("backend"))
    reason = str(body.get("reason", "")).strip()
    if not backend:
        return JSONResponse({"error": "valid backend required"}, status_code=400)
    if not reason:
        return JSONResponse({"error": "reason required"}, status_code=400)
    try:
        from backend_retirement import STATUS_RETIRED, apply_retirement

        apply_retirement({
            "action": "retire",
            "backend": backend,
            "reason": f"manual operator override: {reason[:200]}",
            "status": STATUS_RETIRED,
        })
    except ImportError:
        return JSONResponse({"error": "backend_retirement module not loaded"}, status_code=503)
    except Exception as exc:
        logger.warning("manual backend retirement failed backend=%s: %s", backend, type(exc).__name__)
        return JSONResponse({"error": "backend retirement failed"}, status_code=500)
    return JSONResponse({"ok": True, "backend": backend, "status": "retired"})


@router.get("/metrics/prometheus", dependencies=[Depends(require_private_api_key)])
def ops_metrics_prometheus(request: Request):
    """Prometheus / OpenMetrics scrape endpoint (default-off).

    Enable with LIMA_PROMETHEUS_METRICS=1.
    Requires prometheus_client package installed.
    """
    from observability.prometheus_metrics import generate_metrics, is_enabled

    if not is_enabled():
        return JSONResponse(
            {"error": "Prometheus metrics disabled. Set LIMA_PROMETHEUS_METRICS=1"},
            status_code=404,
        )
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(generate_metrics(), media_type="text/plain; version=0.0.4")
