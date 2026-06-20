"""Layer 4: backend execution with fallback (CQ-014 slice 11)."""

from __future__ import annotations

import logging
import time
from typing import Callable

from routing_executor_fallback import _fallback_phase
from routing_executor_serial import _serial_attempt

MAX_FALLBACKS = 10
MAX_FALLBACKS_TOOLS = 20
PER_BACKEND_TIMEOUT = 15.0

logger = logging.getLogger(__name__)
_log = logger


def execute(
    backends: list[str],
    call_fn: Callable[..., str],
    messages: list[dict],
    max_tokens: int = 4096,
    tools: list[dict] | None = None,
    scenario: str = "",
    request_type: str = "",
) -> tuple[str, str, int]:
    """按序尝试后端，失败则快速 fallback。返回 (backend, answer, error_count)"""
    t0 = time.time()
    max_tries = MAX_FALLBACKS_TOOLS if tools else MAX_FALLBACKS

    result = _serial_attempt(
        backends[:max_tries],
        call_fn,
        messages,
        max_tokens,
        tools,
        scenario,
        request_type,
        attempt_label="serial",
    )
    if result and result[0] is not None:
        return result[0], result[1] or "", result[2]

    serial_errors = result[2] if result else 0
    if backends:
        fb = _fallback_phase(
            backends,
            call_fn,
            messages,
            max_tokens,
            tools,
            scenario,
            request_type,
            t0,
        )
        if fb:
            return fb[0], fb[1], serial_errors

    return "exhausted", "", serial_errors
