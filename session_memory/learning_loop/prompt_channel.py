"""Prompt-profile learning channel."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from .models import TaskOutcome

_log = logging.getLogger(__name__)

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
    except ImportError as exc:
        _log.warning("session_memory.store not installed; prompt profile not saved: %s", exc)

    return {"profile_key": profile_key, "status": outcome.status}


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
