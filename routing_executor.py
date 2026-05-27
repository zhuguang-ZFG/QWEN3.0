"""Layer 4: backend execution with fallback (CQ-014 slice 11)."""

from __future__ import annotations

import logging
import time
from typing import Callable, Optional

MAX_FALLBACKS = 10
MAX_FALLBACKS_TOOLS = 15
PER_BACKEND_TIMEOUT = 12.0

logger = logging.getLogger(__name__)


def execute(backends: list[str],
            call_fn: Callable[[str, list[dict], int], str],
            messages: list[dict],
            max_tokens: int = 4096,
            tools: list[dict] | None = None) -> tuple[str, str, int]:
    """按序尝试后端，失败则快速 fallback。返回 (backend, answer, error_count)"""
    import routing_engine as re

    t0 = time.time()
    errors = 0
    max_tries = MAX_FALLBACKS_TOOLS if tools else MAX_FALLBACKS

    for backend in backends[:max_tries]:
        if re.health_tracker.is_cooled_down(backend):
            errors += 1
            continue
        try:
            t_backend = time.time()
            if tools:
                answer = call_fn(backend, messages, max_tokens, tools=tools)
            else:
                answer = call_fn(backend, messages, max_tokens)
            latency_ms = (time.time() - t_backend) * 1000

            if answer and len(answer.strip()) > 5:
                re.health_tracker.record_success(backend, latency_ms)
                re.budget_manager.record_usage(backend)
                return backend, answer, errors

            re.health_tracker.record_failure(backend, error_code=None)
            errors += 1
        except Exception as e:
            code = extract_error_code(e)
            re.health_tracker.record_failure(backend, error_code=code)
            errors += 1
            if latency_ms > PER_BACKEND_TIMEOUT * 1000:
                logger.warning("[EXECUTE] %s slow (%.0fs), skipping", backend, latency_ms / 1000)

    if not errors and backends:
        re.health_tracker.detect_and_reset_mass_failure()
        for backend in backends[:3]:
            if re.health_tracker.is_cooled_down(backend):
                continue
            try:
                if tools:
                    answer = call_fn(backend, messages, max_tokens, tools=tools)
                else:
                    answer = call_fn(backend, messages, max_tokens)
                if answer and len(answer.strip()) > 5:
                    re.health_tracker.record_success(backend, (time.time() - t0) * 1000)
                    return backend, answer, errors
            except Exception as e:
                re.health_tracker.record_failure(backend, error_code=extract_error_code(e))
                errors += 1

    return "exhausted", "", errors


def extract_error_code(e: Exception) -> Optional[int]:
    for attr in ("status_code", "code", "status"):
        val = getattr(e, attr, None)
        if isinstance(val, int):
            return val
    s = str(e)
    if "429" in s:
        return 429
    if "401" in s:
        return 401
    if "403" in s:
        return 403
    return None
