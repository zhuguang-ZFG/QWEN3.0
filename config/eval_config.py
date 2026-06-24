"""Eval-related environment configuration (P1-2 phase 3).

All eval tuning knobs are read here so that eval modules do not repeat
``os.environ.get()`` calls. Values are resolved at call time so tests can
change the environment without reimporting.

Note: periodic coding eval was retired in v3.0.  The corresponding accessors
remain as stubs returning safe defaults so imports do not break.
"""

from __future__ import annotations

import os


def _truthy(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def eval_base_url() -> str:
    return os.environ.get("LIMA_EVAL_BASE_URL", "http://127.0.0.1:8080").rstrip("/")


def quick_backend_list() -> list[str]:
    raw = os.environ.get(
        "LIMA_EVAL_QUICK_BACKENDS",
        "scnet_qwen30b,scnet_ds_flash,kimi",
    )
    return [b.strip() for b in raw.split(",") if b.strip()]


def full_backend_list() -> list[str]:
    raw = os.environ.get(
        "LIMA_EVAL_FULL_BACKENDS",
        "scnet_large_ds_pro,scnet_qwen30b,scnet_large_ds_flash,scnet_qwen235b,"
        "scnet_ds_flash,scnet_ds_pro,cf_kimi_k26,kimi_search,kimi_thinking,kimi,"
        "stock_kimi_k2",
    )
    return [b.strip() for b in raw.split(",") if b.strip()]


def periodic_eval_enabled() -> bool:
    """Periodic coding eval is retired in v3.0; always disabled."""
    return False


def coding_eval_interval_hours() -> float:
    """Periodic coding eval is retired in v3.0; returns a safe default."""
    return 168.0


def interval_seconds() -> int:
    """Periodic coding eval is retired in v3.0; returns a safe default."""
    return 604800


def periodic_notify_enabled() -> bool:
    return _truthy("LIMA_PERIODIC_EVAL_NOTIFY", "1")


def periodic_full_eval() -> bool:
    return _truthy("LIMA_PERIODIC_CODING_EVAL_FULL", "0")


def pool_gate_enabled() -> bool:
    return os.environ.get("LIMA_EVAL_POOL_GATE", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def min_avg_score(default: float = 1.0) -> float:
    raw = os.environ.get("LIMA_EVAL_POOL_MIN_SCORE", str(default)).strip()
    try:
        return float(raw)
    except ValueError:
        return default
