"""Ops metrics collectors — data gathering from subsystems."""
from __future__ import annotations

import time
from typing import Any

from fastapi import Request

from .formatters import redacted, top_backend_counts, top_backend_details


def app_stats(request: Request) -> dict[str, Any]:
    """Extract app-level stats from request state."""
    state = getattr(request.app, "state", None)
    stats = getattr(state, "stats", {}) if state is not None else {}
    return stats if isinstance(stats, dict) else {}


def recent_agent_tasks(limit: int = 5) -> list[dict[str, Any]]:
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
            "goal": redacted(str(request.get("goal", "")), 60),  # type: ignore[reportOptionalMemberAccess]
        })
    return recent


def get_capability_evidence() -> dict:
    """Fetch capability evidence from observability."""
    try:
        from observability.capability_evidence import recent_evidence
        return {"recent": recent_evidence(limit=10)}
    except ImportError:
        return {"recent": [], "error": "unavailable"}


def get_cli_telemetry() -> dict[str, Any]:
    """Fetch CLI telemetry summary."""
    try:
        from observability.cli_telemetry import cli_telemetry_summary
        return cli_telemetry_summary(limit=10)
    except ImportError:
        return {"total_recent": 0, "recent": [], "error": "unavailable"}


def get_backend_telemetry() -> dict[str, Any]:
    """Fetch backend telemetry summary."""
    try:
        from observability.backend_telemetry import backend_telemetry_summary
        return backend_telemetry_summary(limit=10)
    except ImportError:
        return {"total_recent": 0, "recent": [], "error": "unavailable"}


def get_routing_guard() -> dict[str, Any]:
    """Fetch routing guard snapshot."""
    try:
        from observability.routing_guard import backend_guard_snapshot
        return backend_guard_snapshot(limit=200)
    except ImportError:
        return {"enabled": False, "decisions": {}, "error": "unavailable"}


def backend_recovery_snapshot(dead_backends: list[str], degraded_backends: list[str]) -> dict[str, Any]:
    """Fetch backend recovery snapshot."""
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


def ops_metrics_snapshot(request: Request) -> dict[str, Any]:
    """Unified metrics snapshot across all subsystems."""
    now = time.time()

    # Request stats (injected from server)
    stats = app_stats(request)
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

    recent_tasks = recent_agent_tasks(limit=5)

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

    # Learning loop stats
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
        "backend_calls": top_backend_counts(backend_calls),
        "backend_call_details": top_backend_details(backend_calls),
        "backends": {
            "total": len(health_map),
            "dead": len(dead_backends),
            "degraded": len(degraded_backends),
            "dead_list": dead_backends[:10],
            "error_summary": dict(list(backend_errors.items())[:10]),
            "recovery": backend_recovery_snapshot(dead_backends, degraded_backends),
        },
        "device_gateway": device,
        "agent_workers": agent,
        "learning": learning,
        "retrieval_traces": retrieval_traces,
        "recent_agent_tasks": recent_tasks,
        "cli_telemetry": get_cli_telemetry(),
        "backend_telemetry": get_backend_telemetry(),
        "routing_guard": get_routing_guard(),
        "capability_evidence": get_capability_evidence(),
    }
