# DEPRECATED v3.0 — coding capability retired
"""Filter coding backend pools using latest eval average scores (default off demotion).

DEPRECATED v3.0: Coding capability retired. Functions are kept with safe default
returns to avoid breaking imports, but pool gate is permanently disabled.
"""

from __future__ import annotations

import logging
from pathlib import Path

_log = logging.getLogger(__name__)


def pool_gate_enabled() -> bool:
    """DEPRECATED — always returns False."""
    return False


def min_avg_score() -> float:
    """DEPRECATED — returns 1.0."""
    return 1.0


def average_scores_from_path(path: Path) -> dict[str, float]:
    """DEPRECATED — returns empty dict."""
    return {}


def load_eval_averages(data_dir: Path | None = None) -> dict[str, float]:
    """DEPRECATED — returns empty dict."""
    return {}


def demoted_backends(
    data_dir: Path | None = None,
    *,
    threshold: float | None = None,
) -> frozenset[str]:
    """DEPRECATED — returns empty frozenset."""
    return frozenset()


def filter_coding_pool(
    pool: list[str],
    data_dir: Path | None = None,
    *,
    threshold: float | None = None,
) -> list[str]:
    """DEPRECATED — returns the input pool unchanged."""
    return list(pool)
