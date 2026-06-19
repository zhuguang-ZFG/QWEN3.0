"""Internal helpers for parsing route-evidence artifact logs."""

from __future__ import annotations

import json
import logging
from pathlib import Path

_log = logging.getLogger(__name__)

# Maximum evidence age for history inference (seconds = 7 days)
_MAX_EVIDENCE_AGE_S = 7 * 24 * 3600


def _parse_evidence_log(
    log_path: Path,
    max_age_s: float,
) -> tuple[dict[str, int], set[str], list[float], int, int]:
    """Parse route evidence log and return aggregated stats."""
    models_seen: dict[str, int] = {}
    backends_failed: set[str] = set()
    latencies: list[float] = []
    successes = 0
    total = 0
    for line in log_path.read_text(encoding="utf-8").strip().split("\n"):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = rec.get("timestamp", "")
        age = _age_seconds(ts)
        if age is not None and age > max_age_s:
            continue
        total += 1
        model = rec.get("selected_model", "")
        if model:
            models_seen[model] = models_seen.get(model, 0) + 1
        backend = rec.get("backend", "")
        reason = rec.get("reason", "")
        if backend and ("fail" in reason.lower() or "error" in reason.lower()):
            backends_failed.add(backend)
        rp = rec.get("route_policy", {})
        if isinstance(rp, dict) and rp:
            successes += 1
    return models_seen, backends_failed, latencies, successes, total


def _age_seconds(timestamp: str) -> float | None:
    """Compute age in seconds of an ISO-8601 timestamp.  Returns None on parse failure."""
    from datetime import datetime, timezone

    try:
        dt = datetime.fromisoformat(timestamp)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds()
    except (ValueError, TypeError):
        return None
