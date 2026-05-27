"""Layer 4: backend execution with fallback (CQ-014 slice 11)."""

from __future__ import annotations

import time
from typing import Callable, Optional

MAX_FALLBACKS = 5


def execute(backends: list[str],
            call_fn: Callable[[str, list[dict], int], str],
            messages: list[dict],
            max_tokens: int = 4096,
            tools: list[dict] | None = None) -> tuple[str, str, int]:
    """按序尝试后端，失败则 fallback。返回 (backend, answer, error_count)"""
    import routing_engine as re

    t0 = time.time()
    errors = 0
    tried_any = False

    for backend in backends[:MAX_FALLBACKS]:
        if re.health_tracker.is_cooled_down(backend):
            errors += 1
            continue
        tried_any = True
        try:
            t_backend = time.time()
            if tools:
                answer = call_fn(backend, messages, max_tokens, tools=tools)
            else:
                answer = call_fn(backend, messages, max_tokens)
            if answer and len(answer.strip()) > 5:
                latency_ms = (time.time() - t_backend) * 1000
                re.health_tracker.record_success(backend, latency_ms)
                re.budget_manager.record_usage(backend)
                return backend, answer, errors
            re.health_tracker.record_failure(backend, error_code=None)
            errors += 1
        except Exception as e:
            code = extract_error_code(e)
            if code != 503:
                re.health_tracker.record_failure(backend, error_code=code)
            errors += 1

    if not tried_any:
        re.health_tracker.detect_and_reset_mass_failure()
        for backend in backends[:3]:
            try:
                answer = call_fn(backend, messages, max_tokens, tools=tools)
                if answer and len(answer.strip()) > 5:
                    re.health_tracker.record_success(backend, (time.time() - t0) * 1000)
                    return backend, answer, errors
            except Exception as e:
                import logging
                logging.warning(f"[EXECUTE] force-try {backend} failed: {type(e).__name__}: {e}")
                re.health_tracker.record_failure(backend, error_code=extract_error_code(e))
                errors += 1

    if re.health_tracker.detect_and_reset_mass_failure():
        for b in re.router_v3.DIRECT_BACKENDS[:2]:
            if re.health_tracker.is_cooled_down(b):
                continue
            try:
                answer = call_fn(b, messages, max_tokens)
                if answer and len(answer.strip()) > 5:
                    return b, answer, errors
            except Exception as e:
                re.health_tracker.record_failure(b, error_code=extract_error_code(e))
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
