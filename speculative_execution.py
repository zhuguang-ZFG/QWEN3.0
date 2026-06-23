"""Parallel speculative backend execution and latency learning."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Awaitable, Callable

import budget_manager
import health_tracker
from async_utils import run_coro_sync

logger = logging.getLogger("speculative")

MIN_VALID_LENGTH = 10
_LATENCY_WINDOW = 10
_SLOW_THRESHOLD_MS = 4000

_latency_lock = threading.Lock()
_latency_history: dict[str, list[float]] = {}


def speculative_call(
    backends: list[str],
    call_fn: Callable[[str, list[dict], int], str],
    messages: list[dict],
    max_tokens: int = 4096,
    max_parallel: int = 3,
    timeout_sec: float = 3.0,
    scenario: str = "",
    request_type: str = "",
) -> tuple[str, str, float]:
    async def _wrap_sync(b: str, m: list[dict], mt: int) -> str:
        return await asyncio.to_thread(call_fn, b, m, mt)

    try:
        return run_coro_sync(
            speculative_call_async(
                backends,
                _wrap_sync,
                messages,
                max_tokens,
                max_parallel=max_parallel,
                timeout_sec=timeout_sec,
                scenario=scenario,
                request_type=request_type,
            )
        )
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Speculative execution failed: {e}") from e


async def _spec_worker(
    backend: str,
    async_call_fn: Callable,
    messages: list[dict],
    max_tokens: int,
    scenario: str,
    request_type: str,
) -> str:
    """Single speculative worker: call backend, record metrics."""
    backend_t0 = time.time()
    try:
        result = await async_call_fn(backend, messages, max_tokens)
        latency = (time.time() - backend_t0) * 1000
        _record_latency(backend, latency)
        is_valid = isinstance(result, str) and len(result.strip()) >= MIN_VALID_LENGTH
        _record_backend_attempt(
            backend=backend,
            scenario=scenario,
            request_type=request_type,
            success=is_valid,
            latency_ms=latency,
            response_empty=not is_valid,
            phase="speculative",
            attempt="parallel",
        )
        return result if isinstance(result, str) else ""
    except Exception as e:
        latency = (time.time() - backend_t0) * 1000
        health_tracker.record_failure(backend, error_code=getattr(e, "status_code", 500))
        _record_latency(backend, latency + _SLOW_THRESHOLD_MS)
        _record_backend_attempt(
            backend=backend,
            scenario=scenario,
            request_type=request_type,
            success=False,
            latency_ms=latency,
            status_code=getattr(e, "status_code", 500),
            error=str(e),
            phase="speculative",
            attempt="parallel",
        )
        logger.debug("[SPEC_ASYNC] %s failed: %s", backend, type(e).__name__)
        return ""


async def _spec_race(
    tasks: dict[asyncio.Task, str],
    timeout_sec: float,
) -> tuple[str, str]:
    """Race tasks to find the first valid answer; cancel losers."""
    winner_backend = ""
    winner_answer = ""
    pending = set(tasks.keys())
    deadline = time.monotonic() + timeout_sec
    try:
        while pending and not winner_backend:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            done, pending = await asyncio.wait(
                pending,
                timeout=remaining,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if not done:
                break
            for task in done:
                try:
                    answer = task.result()
                except Exception:
                    continue
                if answer and len(answer.strip()) >= MIN_VALID_LENGTH:
                    winner_backend = tasks[task]
                    winner_answer = answer
                    break
        if pending:
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
    except Exception as exc:
        logger.warning("speculative parallel race failed: %s", exc)
    return winner_backend, winner_answer


async def speculative_call_async(
    backends: list[str],
    async_call_fn: Callable[[str, list[dict], int], Awaitable[object]],
    messages: list[dict],
    max_tokens: int = 4096,
    max_parallel: int = 3,
    timeout_sec: float = 3.0,
    scenario: str = "",
    request_type: str = "",
) -> tuple[str, str, float]:
    candidates = backends[:max_parallel]
    if not candidates:
        raise RuntimeError("No backends available for speculative execution")

    t0 = time.time()
    tasks: dict[asyncio.Task, str] = {
        asyncio.create_task(_spec_worker(b, async_call_fn, messages, max_tokens, scenario, request_type)): b
        for b in candidates
    }

    winner_backend, winner_answer = await _spec_race(tasks, timeout_sec)
    if not winner_backend:
        raise RuntimeError("All speculative backends failed or returned empty")

    latency_ms = (time.time() - t0) * 1000
    health_tracker.record_success(winner_backend, latency_ms)
    budget_manager.record_usage(winner_backend)
    logger.info("[SPEC] winner=%s latency=%.0fms (tried %d)", winner_backend, latency_ms, len(candidates))
    return winner_backend, winner_answer, latency_ms


def _record_latency(backend: str, latency_ms: float):
    with _latency_lock:
        if backend not in _latency_history:
            _latency_history[backend] = []
        _latency_history[backend].append(latency_ms)
        if len(_latency_history[backend]) > _LATENCY_WINDOW:
            _latency_history[backend] = _latency_history[backend][-_LATENCY_WINDOW:]


def is_historically_fast(backend: str) -> bool:
    with _latency_lock:
        history = _latency_history.get(backend)
        if not history or len(history) < 3:
            return True
        avg = sum(history) / len(history)
        return avg < _SLOW_THRESHOLD_MS


def _record_backend_attempt(**kwargs) -> None:
    try:
        from observability.backend_telemetry import record_backend_attempt

        record_backend_attempt(**kwargs)
    except ImportError:
        logger.warning("observability.backend_telemetry not installed; backend telemetry skipped")
