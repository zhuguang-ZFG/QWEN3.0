"""Backward-compatible shim — implementation moved to scripts/eval_loop.py (optional tooling)."""

from __future__ import annotations

import warnings

warnings.warn(
    "根目录 eval_loop 已退役；请使用 scripts/eval_loop.py（可选离线评估工具）",
    DeprecationWarning,
    stacklevel=2,
)

from scripts.eval_loop import (  # noqa: E402
    append_history,
    compare,
    create_default_eval_set,
    promote_if_better,
    run_eval,
    run_full_eval_cycle,
)
from scripts.eval_loop_paths import (  # noqa: E402
    DEFAULT_EVAL_SET_PATH,
    DOMAIN_WEIGHT,
    EVAL_SET_PATH,
    LM_STUDIO_MODEL,
    LM_STUDIO_URL,
    MAX_DOMAIN_DROP,
    RESULTS_DIR,
)

# Legacy name: load bundled items when imported by old notebooks/scripts.
import json

with open(DEFAULT_EVAL_SET_PATH, encoding="utf-8") as _f:
    DEFAULT_EVAL_SET = json.load(_f)

__all__ = [
    "DEFAULT_EVAL_SET",
    "EVAL_SET_PATH",
    "RESULTS_DIR",
    "LM_STUDIO_URL",
    "LM_STUDIO_MODEL",
    "DOMAIN_WEIGHT",
    "MAX_DOMAIN_DROP",
    "create_default_eval_set",
    "run_eval",
    "compare",
    "append_history",
    "promote_if_better",
    "run_full_eval_cycle",
]
