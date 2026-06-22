"""Parallel backend attempt helpers for routing_executor."""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

import budget_manager
from routing_executor_telemetry import (
    _record_backend_attempt,
    extract_error_code,
)

_log = logging.getLogger(__name__)


def _try_one_parallel(
    backend: str,
    call_fn: Callable,
    messages: list[dict],
    max_tokens: int,
    tools: list[dict] | None,
    *,
    scenario: str = "",
    request_type: str = "",
) -> tuple[str, str] | None:
    """Call a single backend for the parallel fallback pool."""
    started = time.time()
    try:
        if tools:
            answer = call_fn(backend, messages, max_tokens, tools=tools)
        else:
            answer = call_fn(backend, messages, max_tokens)
        latency_ms = (time.time() - started) * 1000
        if answer and len(answer.strip()) > 5:
            budget_manager.record_usage(backend)
            _record_backend_attempt(
                backend=backend,
                scenario=scenario,
                request_type=request_type,
                success=True,
                latency_ms=latency_ms,
                tools_requested=bool(tools),
                attempt="parallel_fallback",
            )
            return backend, answer
        _record_backend_attempt(
            backend=backend,
            scenario=scenario,
            request_type=request_type,
            success=False,
            latency_ms=latency_ms,
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
        _log.warning("parallel fallback backend=%s failed: %s", backend, exc)
    return None


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
    with ThreadPoolExecutor(max_workers=len(backends)) as pool:
        futures = {
            pool.submit(
                _try_one_parallel,
                b,
                call_fn,
                messages,
                max_tokens,
                tools,
                scenario=scenario,
                request_type=request_type,
            ): b
            for b in backends
        }
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
