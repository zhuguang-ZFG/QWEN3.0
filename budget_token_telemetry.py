"""Token usage telemetry for budget manager."""

from __future__ import annotations

import logging
import threading
from typing import Any

from budget_cost_class import get_cost_class, should_track_cost

logger = logging.getLogger(__name__)

_token_lock = threading.Lock()
_token_usage: dict[str, dict[str, int]] = {}


def record_token_usage(backend: str, prompt_tokens: int = 0, completion_tokens: int = 0) -> None:
    """Best-effort token tracking from API response.usage."""
    if prompt_tokens <= 0 and completion_tokens <= 0:
        return
    if not should_track_cost(backend):
        return
    with _token_lock:
        entry = _token_usage.setdefault(
            backend,
            {
                "prompt": 0,
                "completion": 0,
                "requests": 0,
            },
        )
        entry["prompt"] += prompt_tokens
        entry["completion"] += completion_tokens
        entry["requests"] += 1

    # Emit token_usage_event to observability (M6-S3)
    try:
        from observability.metrics import record as _obs_record
        from observability.events import token_usage_event

        _obs_record(token_usage_event(backend, prompt_tokens, completion_tokens, get_cost_class(backend)))
    except ImportError:
        logger.debug("observability metrics unavailable: optional dependency not installed")


def get_token_usage(backend: str = "") -> dict[str, Any]:
    """Return token telemetry. Pass empty string for all backends."""
    with _token_lock:
        if backend:
            return dict(_token_usage.get(backend, {"prompt": 0, "completion": 0, "requests": 0}))
        return {k: dict(v) for k, v in _token_usage.items()}


def reset_token_usage() -> None:
    """Clear token telemetry (test helper)."""
    with _token_lock:
        _token_usage.clear()
