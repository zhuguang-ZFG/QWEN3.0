"""Learning loop — feeds LiMa Code task outcomes back into memory, prompt,
routing, and eval systems.

Connects the artifact-bundle outputs from LiMa Code worker runs to:
1. Typed memory: save patterns as routing_lesson, test_result, code_fact
2. Prompt profiles: record task-type → prompt-version → outcome tuples
3. Routing feedback: record backend, route reason, latency, success/failure
4. Eval candidates: gate promotion behind evidence, never auto-change routing

All promotions are evidence-gated. Nothing changes routing behavior
automatically — every learned pattern must pass eval before adoption.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TaskOutcome:
    task_id: str
    status: str  # succeeded | failed | needs_review | blocked
    goal: str = ""
    changed_files: list[str] = field(default_factory=list)
    test_results: list[dict] = field(default_factory=list)
    backend: str = ""
    scenario: str = ""
    latency_ms: int = 0
    failure_reason: str = ""
    artifacts: list[str] = field(default_factory=list)
    worker_id: str = ""


def ingest_task_outcome(outcome: TaskOutcome) -> dict[str, Any]:
    """Feed a completed task outcome into all four learning channels.

    Returns a summary of what was learned (or gated).
    """
    result: dict[str, Any] = {
        "task_id": outcome.task_id,
        "memory": _feed_memory(outcome),
        "prompt": _feed_prompt(outcome),
        "routing": _feed_routing(outcome),
        "eval": _feed_eval(outcome),
    }
    return result


# ── Channel 1: Typed Memory ─────────────────────────────────────────────────

def _feed_memory(outcome: TaskOutcome) -> dict[str, Any]:
    """Extract patterns from task outcome and save as typed memories."""
    saved: list[str] = []

    try:
        from session_memory.store import save_typed_memory

        # Test results → test_result memory
        for tr in outcome.test_results:
            if tr.get("exit_code") == 0:
                save_typed_memory(
                    "test_result",
                    f"PASS: {tr.get('command', '')[:80]} (task {outcome.task_id})",
                    detail=f"exit={tr.get('exit_code')}, duration={tr.get('duration_ms', 0)}ms",
                )
                saved.append("test_result:pass")
            else:
                save_typed_memory(
                    "test_result",
                    f"FAIL: {tr.get('command', '')[:80]} (task {outcome.task_id})",
                    detail=f"exit={tr.get('exit_code')}",
                )
                saved.append("test_result:fail")

        # Task outcome → routing_lesson or code_fact
        if outcome.status in ("succeeded", "needs_review"):
            save_typed_memory(
                "routing_lesson",
                f"task {outcome.task_id}: {outcome.status} via {outcome.backend or 'unknown'}",
                detail=f"scenario={outcome.scenario}, latency={outcome.latency_ms}ms, files={len(outcome.changed_files)}",
            )
            saved.append("routing_lesson:success")
        elif outcome.status in ("failed", "blocked"):
            save_typed_memory(
                "routing_lesson",
                f"task {outcome.task_id}: {outcome.status} — {outcome.failure_reason[:80]}",
                detail=f"via {outcome.backend or 'unknown'}, files={len(outcome.changed_files)}",
            )
            saved.append("routing_lesson:failure")

        # Changed files → code_fact
        for f in outcome.changed_files[:5]:
            save_typed_memory(
                "code_fact",
                f"task {outcome.task_id} changed: {f}",
                detail=f"status={outcome.status}",
            )
        if outcome.changed_files:
            saved.append(f"code_fact:{len(outcome.changed_files)}")

    except ImportError:
        pass

    return {"saved": saved}


# ── Channel 2: Prompt Profile ───────────────────────────────────────────────

_PROMPT_PROFILES: dict[str, list[dict]] = {}

def _feed_prompt(outcome: TaskOutcome) -> dict[str, Any]:
    """Record which prompt profile was used and the outcome.

    Profiles are keyed by (scenario, task_type). Later analysis can compare
    which prompt versions work best for each task type.
    """
    scenario = outcome.scenario or "unknown"
    profile_key = f"{scenario}:{outcome.goal[:40]}"

    entry = {
        "task_id": outcome.task_id,
        "status": outcome.status,
        "backend": outcome.backend,
        "changed_files": len(outcome.changed_files),
        "test_pass": sum(1 for t in outcome.test_results if t.get("exit_code") == 0),
        "test_fail": sum(1 for t in outcome.test_results if t.get("exit_code") != 0),
        "timestamp": time.time(),
    }

    _PROMPT_PROFILES.setdefault(profile_key, []).append(entry)
    if len(_PROMPT_PROFILES.get(profile_key, [])) > 50:
        _PROMPT_PROFILES[profile_key] = _PROMPT_PROFILES[profile_key][-25:]

    try:
        from session_memory.store import save_typed_memory
        save_typed_memory(
            "reference_pattern",
            f"prompt_profile:{profile_key} task={outcome.task_id} status={outcome.status}",
            detail=json.dumps(entry, ensure_ascii=False),
        )
    except ImportError:
        pass

    return {"profile_key": profile_key, "status": outcome.status}


# ── Channel 3: Routing Feedback ─────────────────────────────────────────────

def _feed_routing(outcome: TaskOutcome) -> dict[str, Any]:
    """Record routing decision outcome for future route quality analysis.

    Does NOT change routing weights — only records evidence.
    Route weight changes require explicit eval gate.
    """
    if not outcome.backend:
        return {"recorded": False, "reason": "no backend recorded"}

    feedback: dict[str, Any] = {
        "task_id": outcome.task_id,
        "backend": outcome.backend,
        "scenario": outcome.scenario,
        "status": outcome.status,
        "latency_ms": outcome.latency_ms,
        "timestamp": time.time(),
    }

    try:
        from context_pipeline.routing_weights import get_routing_weights
        rw = get_routing_weights()
        if outcome.status in ("succeeded", "needs_review"):
            rw.record_success(outcome.backend, outcome.scenario)
        else:
            rw.record_failure(outcome.backend, outcome.scenario)
    except ImportError:
        pass

    try:
        from session_memory.store import save_typed_memory
        save_typed_memory(
            "routing_lesson",
            f"route:{outcome.backend} scenario={outcome.scenario} status={outcome.status}",
            detail=json.dumps(feedback, ensure_ascii=False),
        )
    except ImportError:
        pass

    return {"recorded": True, "backend": outcome.backend, "scenario": outcome.scenario}


# ── Channel 4: Eval Candidate ───────────────────────────────────────────────

_EVAL_CANDIDATES: list[dict] = []

def _feed_eval(outcome: TaskOutcome) -> dict[str, Any]:
    """Queue outcome as an eval candidate. Promotion requires evidence.

    Candidates that repeatedly succeed with the same pattern can be promoted
    by an explicit eval run. Nothing is auto-promoted.
    """
    candidate = {
        "task_id": outcome.task_id,
        "backend": outcome.backend,
        "scenario": outcome.scenario,
        "status": outcome.status,
        "test_pass_rate": _test_pass_rate(outcome.test_results),
        "changed_files_count": len(outcome.changed_files),
        "timestamp": time.time(),
    }

    _EVAL_CANDIDATES.append(candidate)
    if len(_EVAL_CANDIDATES) > 200:
        _EVAL_CANDIDATES[:] = _EVAL_CANDIDATES[-100:]

    # Only promote explicit patterns: 3+ successes with same backend+scenario
    if outcome.status in ("succeeded", "needs_review") and outcome.backend:
        _maybe_promote_pattern(outcome)

    return {"candidate_queued": True, "total_candidates": len(_EVAL_CANDIDATES)}


def _test_pass_rate(test_results: list[dict]) -> float:
    if not test_results:
        return 1.0
    passed = sum(1 for t in test_results if t.get("exit_code") == 0)
    return passed / len(test_results)


def _maybe_promote_pattern(outcome: TaskOutcome) -> None:
    """Check if a backend+scenario pattern has enough evidence to promote.

    Requires: 3+ successes with same backend+scenario from different tasks.
    Only records as a reference_pattern — does NOT change routing pools.
    """
    matches = [
        c for c in _EVAL_CANDIDATES
        if c["backend"] == outcome.backend
        and c["scenario"] == outcome.scenario
        and c["status"] in ("succeeded", "needs_review")
        and c["task_id"] != outcome.task_id
    ]
    if len(matches) >= 3:
        try:
            from session_memory.store import save_typed_memory, query_by_type
            existing = query_by_type("reference_pattern", limit=5)
            already_promoted = any(
                f"promoted:{outcome.backend}:{outcome.scenario}" in (e.summary or "")
                for e in existing
            )
            if not already_promoted:
                save_typed_memory(
                    "reference_pattern",
                    f"promoted:{outcome.backend}:{outcome.scenario} — {len(matches)+1} successes",
                    detail=json.dumps({
                        "backend": outcome.backend,
                        "scenario": outcome.scenario,
                        "evidence_count": len(matches) + 1,
                        "latest_task": outcome.task_id,
                        "promoted_at": time.time(),
                    }, ensure_ascii=False),
                )
        except ImportError:
            pass


# ── Public query helpers ─────────────────────────────────────────────────────

def get_prompt_profile_stats() -> dict[str, Any]:
    """Return summary stats per prompt profile (for ops metrics)."""
    stats: dict[str, dict] = {}
    for key, entries in _PROMPT_PROFILES.items():
        total = len(entries)
        succeeded = sum(1 for e in entries if e["status"] in ("succeeded", "needs_review"))
        stats[key] = {
            "total": total,
            "success_rate": succeeded / total if total else 0,
            "last_status": entries[-1]["status"] if entries else "unknown",
        }
    return stats


def get_eval_candidates(limit: int = 20) -> list[dict]:
    """Return recent eval candidates (for ops/admin inspection)."""
    return _EVAL_CANDIDATES[-limit:]


def ingest_from_agent_task_result(
    result: dict[str, Any],
    *,
    backend: str = "",
    scenario: str = "",
    latency_ms: int = 0,
) -> dict[str, Any]:
    """Convenience: ingest a LiMa agent task result dict into the learning loop.

    Accepts the result format that LiMa Server receives from LiMa Code worker
    submissions (the LiMaAgentTaskResult contract).
    """
    outcome = TaskOutcome(
        task_id=str(result.get("task_id", "")),
        status=str(result.get("status", "unknown")),
        goal=str(result.get("summary", ""))[:120],
        changed_files=list(result.get("changed_files", []) or []),
        test_results=list(result.get("test_results", []) or []),
        backend=backend,
        scenario=scenario,
        latency_ms=latency_ms,
        failure_reason=str(result.get("summary", "")) if result.get("status") in ("failed", "blocked") else "",
        artifacts=list(result.get("artifacts", []) or []),
    )
    return ingest_task_outcome(outcome)
