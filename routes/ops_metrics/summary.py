"""Ops metrics summary helpers."""

from __future__ import annotations

from typing import Any


def alert(severity: str, code: str, message: str, count: int = 1) -> dict[str, Any]:
    return {
        "severity": severity,
        "code": code,
        "message": message,
        "count": count,
    }


def extract_metrics_sections(metrics: dict) -> tuple[dict, dict, dict, dict, dict]:
    """Extract and validate metrics subsections."""
    backends = metrics.get("backends")
    backends = backends if isinstance(backends, dict) else {}
    recovery = backends.get("recovery")
    recovery = recovery if isinstance(recovery, dict) else {}
    cli = metrics.get("cli_telemetry")
    cli = cli if isinstance(cli, dict) else {}
    backend_telemetry = metrics.get("backend_telemetry")
    backend_telemetry = backend_telemetry if isinstance(backend_telemetry, dict) else {}
    routing_guard = metrics.get("routing_guard")
    routing_guard = routing_guard if isinstance(routing_guard, dict) else {}
    return backends, recovery, cli, backend_telemetry, routing_guard


def build_ops_alerts(
    backends: dict,
    recovery: dict,
    cli: dict,
    backend_telemetry: dict,
    routing_guard: dict,
) -> list[dict]:
    """Build alert list from metrics sections."""
    dead = int(backends.get("dead", 0) or 0)
    degraded = int(backends.get("degraded", 0) or 0)
    retired = int(recovery.get("retired_count", 0) or 0)
    decisions = routing_guard.get("decisions")
    decisions = decisions if isinstance(decisions, dict) else {}
    quarantined = sum(1 for v in decisions.values() if isinstance(v, dict) and v.get("status") == "quarantined")
    probe_candidates = recovery.get("probe_candidates", [])
    probe_count = len(probe_candidates) if isinstance(probe_candidates, list) else 0

    alerts: list[dict] = []
    if dead:
        alerts.append(alert("critical", "backend_dead", f"{dead} backend(s) are dead", dead))
    if degraded:
        alerts.append(alert("warning", "backend_degraded", f"{degraded} backend(s) are degraded", degraded))
    if retired:
        alerts.append(alert("warning", "backend_retired", f"{retired} backend(s) are manually retired", retired))
    if quarantined:
        alerts.append(alert("warning", "backend_quarantined", f"{quarantined} backend(s) are quarantined", quarantined))
    if int(cli.get("failed_recent", 0) or 0):
        alerts.append(
            alert(
                "warning",
                "cli_failures",
                "Recent developer-tool CLI failures observed",
                int(cli.get("failed_recent", 0)),
            )
        )
    if int(backend_telemetry.get("slow_recent", 0) or 0):
        alerts.append(
            alert(
                "warning",
                "slow_backends",
                "Recent slow backend attempts observed",
                int(backend_telemetry.get("slow_recent", 0)),
            )
        )
    if probe_count:
        alerts.append(
            alert("info", "probe_candidates", "Backends are ready for manual probe/recovery review", probe_count)
        )
    return alerts


def ops_summary_from_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    backends, recovery, cli, backend_telemetry, routing_guard = extract_metrics_sections(metrics)
    alerts = build_ops_alerts(backends, recovery, cli, backend_telemetry, routing_guard)

    dead = int(backends.get("dead", 0) or 0)
    degraded = int(backends.get("degraded", 0) or 0)
    retired = int(recovery.get("retired_count", 0) or 0)
    probe_candidates = recovery.get("probe_candidates", [])
    probe_count = len(probe_candidates) if isinstance(probe_candidates, list) else 0
    decisions = routing_guard.get("decisions")
    decisions = decisions if isinstance(decisions, dict) else {}
    quarantined = sum(1 for v in decisions.values() if isinstance(v, dict) and v.get("status") == "quarantined")

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
