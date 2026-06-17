"""Layer 4: backend execution with fallback (CQ-014 slice 11)."""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

import budget_manager
import health_tracker

MAX_FALLBACKS = 10
MAX_FALLBACKS_TOOLS = 20
PER_BACKEND_TIMEOUT = 15.0

logger = logging.getLogger(__name__)
_log = logger


def _serial_attempt(
    backends: list[str],
    call_fn: Callable[..., str],
    messages: list[dict],
    max_tokens: int,
    tools: list[dict] | None,
    scenario: str,
    request_type: str,
    attempt_label: str,
) -> tuple[str | None, str | None, int]:
    """Try backends sequentially; return (backend, answer, error_count) or None."""
    errors = 0
    for backend in backends:
        if health_tracker.is_cooled_down(backend):
            _record_backend_attempt(
                backend=backend,
                scenario=scenario,
                request_type=request_type,
                success=False,
                latency_ms=0,
                tools_requested=bool(tools),
                status_code=503,
                error="cooled down",
                attempt=attempt_label,
            )
            errors += 1
            continue
        try:
            t_backend = time.time()
            answer = (
                call_fn(backend, messages, max_tokens, tools=tools) if tools else call_fn(backend, messages, max_tokens)
            )
            latency_ms = (time.time() - t_backend) * 1000
            if answer and len(answer.strip()) > 5:
                health_tracker.record_success(backend, latency_ms)
                budget_manager.record_usage(backend)
                _record_backend_attempt(
                    backend=backend,
                    scenario=scenario,
                    request_type=request_type,
                    success=True,
                    latency_ms=latency_ms,
                    tools_requested=bool(tools),
                    attempt=attempt_label,
                )
                return backend, answer, errors
            health_tracker.record_failure(backend, error_code=None)
            _record_backend_attempt(
                backend=backend,
                scenario=scenario,
                request_type=request_type,
                success=False,
                latency_ms=latency_ms,
                tools_requested=bool(tools),
                response_empty=True,
                attempt=attempt_label,
            )
            errors += 1
        except Exception as e:
            latency_ms = (time.time() - t_backend) * 1000
            code = extract_error_code(e)
            health_tracker.record_failure(backend, error_code=code)
            _record_backend_attempt(
                backend=backend,
                scenario=scenario,
                request_type=request_type,
                success=False,
                latency_ms=latency_ms,
                tools_requested=bool(tools),
                status_code=code,
                error=str(e),
                attempt=attempt_label,
            )
            errors += 1
            if latency_ms > PER_BACKEND_TIMEOUT * 1000:
                logger.warning("[EXECUTE] %s slow (%.0fs), skipping", backend, latency_ms / 1000)
    return None, None, errors


def _fallback_phase(
    backends: list[str],
    call_fn: Callable[..., str],
    messages: list[dict],
    max_tokens: int,
    tools: list[dict] | None,
    scenario: str,
    request_type: str,
    t0: float,
) -> tuple[str, str] | None:
    """Mass-fallback: parallel then serial retry of available candidates."""
    health_tracker.detect_and_reset_mass_failure()
    candidates = [
        b for b in backends[:8] if not health_tracker.is_cooled_down(b) and budget_manager.is_budget_available(b)
    ][:3]
    if len(candidates) >= 2:
        result = _parallel_fallback(
            candidates,
            call_fn,
            messages,
            max_tokens,
            tools,
            scenario=scenario,
            request_type=request_type,
        )
        if result:
            backend, answer = result
            health_tracker.record_success(backend, (time.time() - t0) * 1000)
            return backend, answer
    # Serial fallback for remaining candidates
    for backend in candidates:
        if health_tracker.is_cooled_down(backend):
            continue
        try:
            answer = (
                call_fn(backend, messages, max_tokens, tools=tools) if tools else call_fn(backend, messages, max_tokens)
            )
            if answer and len(answer.strip()) > 5:
                health_tracker.record_success(backend, (time.time() - t0) * 1000)
                _record_backend_attempt(
                    backend=backend,
                    scenario=scenario,
                    request_type=request_type,
                    success=True,
                    latency_ms=(time.time() - t0) * 1000,
                    tools_requested=bool(tools),
                    attempt="serial_fallback",
                )
                return backend, answer
        except Exception as exc:
            _record_backend_attempt(
                backend=backend,
                scenario=scenario,
                request_type=request_type,
                success=False,
                latency_ms=(time.time() - t0) * 1000,
                tools_requested=bool(tools),
                status_code=extract_error_code(exc),
                error=str(exc),
                attempt="serial_fallback",
            )
            _log.debug("routing_executor.py: {}", type(exc).__name__)
    return None


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


def _parallel_fallback(
    backends: list[str],
    call_fn: Callable,
    messages: list[dict],
    max_tokens: int,
    tools: list[dict] | None,
    *,
    scenario: str = "",
    request_type: str = "",
) -> tuple[str, str] | None:
    """Try multiple backends in parallel, return first valid response."""

    def _try_one(backend: str) -> tuple[str, str] | None:
        started = time.time()
        try:
            if tools:
                answer = call_fn(backend, messages, max_tokens, tools=tools)
            else:
                answer = call_fn(backend, messages, max_tokens)
            if answer and len(answer.strip()) > 5:
                _record_backend_attempt(
                    backend=backend,
                    scenario=scenario,
                    request_type=request_type,
                    success=True,
                    latency_ms=(time.time() - started) * 1000,
                    tools_requested=bool(tools),
                    attempt="parallel_fallback",
                )
                return backend, answer
            _record_backend_attempt(
                backend=backend,
                scenario=scenario,
                request_type=request_type,
                success=False,
                latency_ms=(time.time() - started) * 1000,
                tools_requested=bool(tools),
                response_empty=True,
                attempt="parallel_fallback",
            )
        except Exception as exc:
            _record_backend_attempt(
                backend=backend,
                scenario=scenario,
                request_type=request_type,
                success=False,
                latency_ms=(time.time() - started) * 1000,
                tools_requested=bool(tools),
                status_code=extract_error_code(exc),
                error=str(exc),
                attempt="parallel_fallback",
            )
            _log.debug("routing_executor.py: {}", type(exc).__name__)
        return None

    with ThreadPoolExecutor(max_workers=len(backends)) as pool:
        futures = {pool.submit(_try_one, b): b for b in backends}
        for future in as_completed(futures):
            try:
                result = future.result()
                if result:
                    for f in futures:
                        f.cancel()
                    return result
            except Exception:
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


def _record_backend_attempt(**kwargs) -> None:
    try:
        from observability.backend_telemetry import record_backend_attempt

        record_backend_attempt(**kwargs)
    except ImportError:
        _log.debug("observability.backend_telemetry not installed; backend telemetry skipped")
