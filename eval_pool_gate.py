"""Filter coding backend pools using latest eval average scores (default off demotion)."""

from __future__ import annotations

import json
import logging
import statistics
from pathlib import Path

from config import eval_config
from eval_slice_summary import latest_scores_path

_log = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent
_DEFAULT_MIN = 1.0


def pool_gate_enabled() -> bool:
    return eval_config.pool_gate_enabled()


def min_avg_score() -> float:
    return eval_config.min_avg_score(_DEFAULT_MIN)


def average_scores_from_path(path: Path) -> dict[str, float]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        return {}
    by_backend: dict[str, list[float]] = {}
    for row in raw:
        if not isinstance(row, dict):
            continue
        backend = str(row.get("backend") or "").strip()
        if not backend:
            continue
        by_backend.setdefault(backend, []).append(float(row.get("score") or 0))
    return {backend: statistics.mean(scores) for backend, scores in by_backend.items() if scores}


def load_eval_averages(data_dir: Path | None = None) -> dict[str, float]:
    base = data_dir or (_ROOT / "data")
    path = latest_scores_path(base, full=True) or latest_scores_path(base, full=False)
    if not path:
        return {}
    try:
        return average_scores_from_path(path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        _log.warning("eval pool gate skipped path=%s err=%s", path, type(exc).__name__)
        return {}


def demoted_backends(
    data_dir: Path | None = None,
    *,
    threshold: float | None = None,
) -> frozenset[str]:
    """Backends whose eval avg score is strictly below threshold."""
    if not pool_gate_enabled():
        return frozenset()
    scores = load_eval_averages(data_dir)
    if not scores:
        return frozenset()
    cutoff = min_avg_score() if threshold is None else threshold
    return frozenset(backend for backend, avg in scores.items() if avg < cutoff)


def filter_coding_pool(
    pool: list[str],
    data_dir: Path | None = None,
    *,
    threshold: float | None = None,
) -> list[str]:
    """Drop eval-demoted backends while preserving order."""
    blocked = demoted_backends(data_dir, threshold=threshold)
    if not blocked:
        return list(pool)
    return [name for name in pool if name not in blocked]
