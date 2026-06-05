"""Layer 4: backend execution with fallback (CQ-014 slice 11)."""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

MAX_FALLBACKS = 10
MAX_FALLBACKS_TOOLS = 20
PER_BACKEND_TIMEOUT = 15.0

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
            latency_ms = 0.0
            if tools:
                answer = call_fn(backend, messages, max_tokens, tools=tools)
            else:
                answer = call_fn(backend, messages, max_tokens)
            latency_ms = (time.time() - t_backend) * 1000

            if answer and len(answer.strip()) > 0:
                re.health_tracker.record_success(backend, latency_ms)
                re.budget_manager.record_usage(backend)
                return backend, answer, errors

            re.health_tracker.record_failure(backend, error_code=None)
            errors += 1
        except Exception as e:
            # Context overflow: stop fallback immediately, propagate to client
            if getattr(e, "is_overflow", False):
                logger.warning("[EXECUTE] %s context overflow, stopping fallback", backend)
                raise
            # M-OC8: OpenCode-style retry policy (session/retry.ts)
            from opencode_retry_policy import is_retryable_error
            if getattr(e, "is_retryable", False) or is_retryable_error(e):
                code = extract_error_code(e)
                re.health_tracker.record_failure(backend, error_code=code)
                errors += 1
                logger.info(
                    "[EXECUTE] %s retryable stream error, falling back (code=%s)",
                    backend,
                    code,
                )
                continue
            code = extract_error_code(e)
            re.health_tracker.record_failure(backend, error_code=code)
            errors += 1
            if latency_ms > PER_BACKEND_TIMEOUT * 1000:
                logger.warning("[EXECUTE] %s slow (%.0fs), skipping", backend, latency_ms / 1000)

    if backends:
        re.health_tracker.detect_and_reset_mass_failure()
        # Parallel fallback: try 3 backends simultaneously, first valid wins
        candidates = [
            b for b in backends[:8]
            if not re.health_tracker.is_cooled_down(b)
            and re.budget_manager.is_budget_available(b)
        ][:3]
        if len(candidates) >= 2:
            result = _parallel_fallback(
                candidates, call_fn, messages, max_tokens, tools, re,
            )
            if result:
                backend, answer = result
                re.health_tracker.record_success(backend, (time.time() - t0) * 1000)
                return backend, answer, errors
        # Serial fallback for remaining
        for backend in candidates:
            if re.health_tracker.is_cooled_down(backend):
                continue
            try:
                if tools:
                    answer = call_fn(backend, messages, max_tokens, tools=tools)
                else:
                    answer = call_fn(backend, messages, max_tokens)
                if answer and len(answer.strip()) > 0:
                    re.health_tracker.record_success(backend, (time.time() - t0) * 1000)
                    return backend, answer, errors
            except Exception as exc:
                # Context overflow: stop serial fallback immediately
                if getattr(exc, "is_overflow", False):
                    logger.warning("[EXECUTE] %s context overflow in serial fallback, stopping", backend)
                    raise
                from opencode_retry_policy import is_retryable_error as _is_retryable
                if getattr(exc, "is_retryable", False) or _is_retryable(exc):
                    logger.info(
                        "[EXECUTE] serial fallback %s retryable error, continuing",
                        backend,
                    )
                    continue
                logger.warning("[EXECUTE] serial fallback %s failed: %s", backend, type(exc).__name__)

    return "exhausted", "", errors


def _parallel_fallback(
    backends: list[str],
    call_fn: Callable,
    messages: list[dict],
    max_tokens: int,
    tools: list[dict] | None,
    re,
) -> tuple[str, str] | None:
    """Try multiple backends in parallel, return first valid response."""
    def _try_one(backend: str) -> tuple[str, str] | None:
        try:
            if tools:
                answer = call_fn(backend, messages, max_tokens, tools=tools)
            else:
                answer = call_fn(backend, messages, max_tokens)
            if answer and len(answer.strip()) > 0:
                return backend, answer
        except Exception as exc:
            # Context overflow: propagate immediately from parallel fallback
            if getattr(exc, "is_overflow", False):
                logger.warning("[EXECUTE] %s context overflow in parallel fallback", backend)
                raise
            from opencode_retry_policy import is_retryable_error as _is_retryable
            if getattr(exc, "is_retryable", False) or _is_retryable(exc):
                logger.debug("[EXECUTE] parallel fallback %s retryable error", backend)
                return None
            logger.debug("[EXECUTE] parallel fallback %s failed: %s", backend, type(exc).__name__)
        return None

    with ThreadPoolExecutor(max_workers=len(backends)) as pool:
        futures = {pool.submit(_try_one, b): b for b in backends}
        for future in as_completed(futures):
            try:
                result = future.result()
                if result:
                    # Cancel remaining futures
                    for f in futures:
                        f.cancel()
                    return result
            except Exception as exc:
                # Context overflow: propagate from parallel result
                if getattr(exc, "is_overflow", False):
                    raise
                logger.debug("[EXECUTE] parallel result error: %s", type(exc).__name__)
                continue
    return None


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
