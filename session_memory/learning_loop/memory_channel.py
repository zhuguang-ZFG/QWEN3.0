"""Typed-memory learning channel."""

from __future__ import annotations

import logging
from typing import Any

from .models import TaskOutcome

_log = logging.getLogger(__name__)


def _save_test_result_memories(outcome: TaskOutcome, saved: list[str]) -> None:
    """Save test_result typed memories for each test result."""
    from session_memory.store import save_typed_memory

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


def _save_outcome_memory(outcome: TaskOutcome, saved: list[str]) -> None:
    """Save routing_lesson typed memory based on task outcome status."""
    from session_memory.store import save_typed_memory

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


def _save_changed_file_memories(outcome: TaskOutcome, saved: list[str]) -> None:
    """Save code_fact typed memories for changed files."""
    from session_memory.store import save_typed_memory

    for f in outcome.changed_files[:5]:
        save_typed_memory(
            "code_fact",
            f"task {outcome.task_id} changed: {f}",
            detail=f"status={outcome.status}",
        )
    if outcome.changed_files:
        saved.append(f"code_fact:{len(outcome.changed_files)}")


def _feed_memory(outcome: TaskOutcome) -> dict[str, Any]:
    """Extract patterns from task outcome and save as typed memories."""
    saved: list[str] = []

    try:
        _save_test_result_memories(outcome, saved)
        _save_outcome_memory(outcome, saved)
        _save_changed_file_memories(outcome, saved)
    except ImportError as exc:
        _log.warning("session_memory.store not installed; typed memory not saved: %s", exc)

    return {"saved": saved}
