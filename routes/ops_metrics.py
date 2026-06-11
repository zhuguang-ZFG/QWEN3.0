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
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from access_guard import require_private_api_key
from routes.json_body import read_json_object
from routes.ops_metrics import ops_metrics_snapshot

router = APIRouter(prefix="/v1/ops")
logger = logging.getLogger(__name__)
_BACKEND_NAME_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,96}$")

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
    return JSONResponse(ops_metrics_snapshot(request))


@router.get("/summary", dependencies=[Depends(require_private_api_key)])
async def ops_summary(request: Request) -> JSONResponse:
    return JSONResponse(_ops_summary_from_metrics(ops_metrics_snapshot(request)))


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
    try:
        from observability import prometheus_metrics
    except ImportError as exc:
        logger.warning("Prometheus metrics module unavailable: %s", exc)
        return JSONResponse({"error": "Prometheus metrics unavailable"}, status_code=503)

    if not prometheus_metrics.is_enabled():
        return JSONResponse(
            {"error": "Prometheus metrics disabled"},
            status_code=404,
        )
    from fastapi.responses import PlainTextResponse
    try:
        body = prometheus_metrics.generate_metrics()
    except RuntimeError as exc:
        logger.warning("Prometheus metrics generation failed: %s", exc)
        return JSONResponse({"error": "Prometheus metrics unavailable"}, status_code=503)
    return PlainTextResponse(body, media_type="text/plain; version=0.0.4")
