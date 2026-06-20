"""Sequential backend attempt helpers for routing_executor."""

from __future__ import annotations

import logging
import time
from typing import Callable

import budget_manager
import health_tracker
from routing_executor_telemetry import (
    _record_backend_attempt,
    extract_error_code,
)

PER_BACKEND_TIMEOUT = 15.0
_log = logging.getLogger(__name__)


def _record_attempt(
    backend: str,
    scenario: str,
    request_type: str,
    tools: list[dict] | None,
    attempt_label: str,
    success: bool,
    latency_ms: float,
    **extra,
) -> None:
    _record_backend_attempt(
        backend=backend,
        scenario=scenario,
        request_type=request_type,
        success=success,
        latency_ms=latency_ms,
        tools_requested=bool(tools),
        attempt=attempt_label,
        **extra,
    )


def _call_one_backend_serial(
    backend: str,
    call_fn: Callable[..., str],
    messages: list[dict],
    max_tokens: int,
    tools: list[dict] | None,
    scenario: str,
    request_type: str,
    attempt_label: str,
) -> str | None:
    """Call a single backend and return the answer, or None on empty/error."""
    try:
        t_backend = time.time()
        answer = (
            call_fn(backend, messages, max_tokens, tools=tools) if tools else call_fn(backend, messages, max_tokens)
        )
        latency_ms = (time.time() - t_backend) * 1000
        if answer and len(answer.strip()) > 5:
            health_tracker.record_success(backend, latency_ms)
            budget_manager.record_usage(backend)
            _record_attempt(
                backend, scenario, request_type, tools, attempt_label, True, latency_ms
            )
            return answer
        health_tracker.record_failure(backend, error_code=None)
        _record_attempt(
            backend, scenario, request_type, tools, attempt_label, False, latency_ms, response_empty=True
        )
        return None
    except Exception as e:
        latency_ms = (time.time() - t_backend) * 1000
        code = extract_error_code(e)
        health_tracker.record_failure(backend, error_code=code)
        _record_attempt(
            backend,
            scenario,
            request_type,
            tools,
            attempt_label,
            False,
            latency_ms,
            status_code=code,
            error=str(e),
        )
        if latency_ms > PER_BACKEND_TIMEOUT * 1000:
            _log.warning("[EXECUTE] %s slow (%.0fs), skipping", backend, latency_ms / 1000)
        return None


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
        answer = _call_one_backend_serial(
            backend,
            call_fn,
            messages,
            max_tokens,
            tools,
            scenario,
            request_type,
            attempt_label,
        )
        if answer is not None:
            return backend, answer, errors
        errors += 1
    return None, None, errors
