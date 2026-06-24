# DEPRECATED v3.0 — coding capability retired
"""Summarize latest coding-backend eval JSON for operators.

DEPRECATED v3.0: Coding capability retired. Functions are kept with safe default
returns to avoid breaking imports, but eval summary is permanently disabled.
"""

from __future__ import annotations

from pathlib import Path


def latest_scores_path(data_dir: Path | None = None, *, full: bool = False) -> Path | None:
    """DEPRECATED — always returns None."""
    return None


def summarize_eval_json(path: Path, *, top_n: int = 5) -> str:
    """DEPRECATED — returns empty string."""
    return ""
