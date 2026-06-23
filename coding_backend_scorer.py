"""coding_backend_scorer.py — Dynamic coding quality scoring for routing.

Loads coding_backend_scores from data/ and provides per-backend quality weights
used by routing_selector to prefer proven coding backends.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path

_log = logging.getLogger(__name__)

SCORE_FILE = Path(__file__).parent / "data" / "coding_backend_scores_full_20260526.json"

_cache: dict[str, float] | None = None
_cache_mtime: float = 0


def _load_scores() -> dict[str, float]:
    """Load and aggregate coding backend scores. Returns {backend: weight_0_to_1}."""
    global _cache, _cache_mtime
    try:
        mtime = SCORE_FILE.stat().st_mtime if SCORE_FILE.exists() else 0
    except OSError:
        mtime = 0

    if _cache is not None and mtime == _cache_mtime:
        return _cache

    scores: dict[str, list[float]] = defaultdict(list)
    try:
        with open(SCORE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        for item in data:
            name = item.get("backend", "")
            score = item.get("score", 0)
            if name and isinstance(score, (int, float)):
                scores[name].append(float(score))
    except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
        _log.warning("Failed to load coding scores: %s", e, exc_info=True)
        _cache = {}
        _cache_mtime = mtime
        return _cache

    weights: dict[str, float] = {}
    for name, sc_list in scores.items():
        avg = sum(sc_list) / len(sc_list)
        # Convert to weight: 100% → 1.5, 50% → 1.0, 0% → 0.3
        weights[name] = 0.3 + avg / 100 * 1.2

    _cache = weights
    _cache_mtime = mtime
    return _cache


def get_coding_weight(backend: str) -> float:
    """Get coding quality weight for a backend. Returns 1.0 if unknown."""
    return _load_scores().get(backend, 1.0)


def get_coding_tier(backend: str) -> str:
    """Classify backend into coding tier: 'proven' | 'fallback' | 'skip' | 'unknown'."""
    w = get_coding_weight(backend)
    if w >= 1.2:
        return "proven"
    if w >= 0.7:
        return "fallback"
    if w > 0:
        return "skip"
    return "unknown"


def refresh() -> None:
    """Force reload of coding scores from disk."""
    global _cache
    _cache = None
    _load_scores()
