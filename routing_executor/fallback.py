"""Fallback phase helpers for routing_executor."""

from __future__ import annotations

import logging
import time
from typing import Callable

import budget_manager
import health_tracker
from .parallel import _parallel_fallback
from .telemetry import (
    _record_backend_attempt,
    extract_error_code,
)

_log = logging.getLogger(__name__)


def _select_fallback_candidates(backends: list[str]) -> list[str]:
    """Pick up to 3 healthy, in-budget candidates for mass fallback."""
    health_tracker.detect_and_reset_mass_failure()
    return [b for b in backends[:8] if not health_tracker.is_cooled_down(b) and budget_manager.is_budget_available(b)][
        :3
    ]


def _serial_fallback_attempt(
    candidates: list[str],
    call_fn: Callable[..., str],
    messages: list[dict],
    max_tokens: int,
    tools: list[dict] | None,
    scenario: str,
    request_type: str,
    t0: float,
) -> tuple[str, str] | None:
    """Try fallback candidates sequentially."""
    for backend in candidates:
        if health_tracker.is_cooled_down(backend):
            continue
        try:
            answer = (
                call_fn(backend, messages, max_tokens, tools=tools) if tools else call_fn(backend, messages, max_tokens)
            )
            if answer and len(answer.strip()) > 5:
                latency_ms = (time.time() - t0) * 1000
                health_tracker.record_success(backend, latency_ms)
                budget_manager.record_usage(backend)
                _record_backend_attempt(
                    backend=backend,
                    scenario=scenario,
                    request_type=request_type,
                    success=True,
                    latency_ms=latency_ms,
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
            _log.warning("serial fallback backend=%s failed: %s", backend, exc)
    return None


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
    candidates = _select_fallback_candidates(backends)
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
    return _serial_fallback_attempt(
        candidates,
        call_fn,
        messages,
        max_tokens,
        tools,
        scenario,
        request_type,
        t0,
    )
