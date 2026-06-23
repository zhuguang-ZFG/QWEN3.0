"""Parallel speculative backend execution and latency learning.

Simple queries are sent to several fast backends in parallel; the first
backend that returns a valid answer wins. The implementation is intentionally
synchronous because the public caller (``routing_engine.route``) is synchronous.
Using a ``ThreadPoolExecutor`` directly avoids the nested event-loop/thread
problem that came from bridging sync code through ``run_coro_sync`` + async
workers.
"""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from typing import Callable

import budget_manager
import health_tracker

logger = logging.getLogger("speculative")

MIN_VALID_LENGTH = 10
_LATENCY_WINDOW = 10
_SLOW_THRESHOLD_MS = 4000

_latency_lock = threading.Lock()
_latency_history: dict[str, list[float]] = {}


def _submit_workers(
    executor: ThreadPoolExecutor,
    candidates: list[str],
    call_fn: Callable[[str, list[dict], int], str],
    messages: list[dict],
    max_tokens: int,
    scenario: str,
    request_type: str,
) -> dict[Future[str], str]:
    """Submit a worker for each candidate backend and map futures to backend names."""
    futures: dict[Future[str], str] = {}
    for backend in candidates:
        future = executor.submit(
            _spec_worker,
            backend,
            call_fn,
            messages,
            max_tokens,
            scenario,
            request_type,
        )
        futures[future] = backend
    return futures


def _shutdown_executor(
    executor: ThreadPoolExecutor,
    futures: dict[Future[str], str],
) -> None:
    """Cancel pending futures and shut down the pool without waiting."""
    for future in futures:
        if not future.done():
            future.cancel()
    executor.shutdown(wait=False)


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
    """Execute speculative backends in parallel; return (backend, answer, latency_ms)."""
    candidates = backends[:max_parallel]
    if not candidates:
        raise RuntimeError("No backends available for speculative execution")

    t0 = time.time()
    executor = ThreadPoolExecutor(max_workers=max_parallel, thread_name_prefix="spec")
    try:
        futures = _submit_workers(executor, candidates, call_fn, messages, max_tokens, scenario, request_type)
        winner_backend, winner_answer = _spec_race(futures, timeout_sec)
    finally:
        _shutdown_executor(executor, futures)

    if not winner_backend:
        raise RuntimeError("All speculative backends failed or returned empty")

    latency_ms = (time.time() - t0) * 1000
    health_tracker.record_success(winner_backend, latency_ms)
    budget_manager.record_usage(winner_backend)
    logger.info(
        "[SPEC] winner=%s latency=%.0fms (tried %d)",
        winner_backend,
        latency_ms,
        len(candidates),
    )
    return winner_backend, winner_answer, latency_ms


def _spec_worker(
    backend: str,
    call_fn: Callable[[str, list[dict], int], str],
    messages: list[dict],
    max_tokens: int,
    scenario: str,
    request_type: str,
) -> str:
    """Single speculative worker: call backend, record metrics."""
    backend_t0 = time.time()
    try:
        result = call_fn(backend, messages, max_tokens)
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
        logger.warning("[SPEC] %s failed: %s", backend, e, exc_info=True)
        return ""


def _spec_race(
    futures: dict[Future[str], str],
    timeout_sec: float,
) -> tuple[str, str]:
    """Race tasks to find the first valid answer; abandon losers."""
    winner_backend = ""
    winner_answer = ""
    try:
        for future in as_completed(futures, timeout=timeout_sec):
            backend = futures[future]
            try:
                answer = future.result()
            except Exception:
                continue
            if answer and len(answer.strip()) >= MIN_VALID_LENGTH:
                winner_backend = backend
                winner_answer = answer
                break
    except Exception as exc:
        logger.warning("speculative parallel race failed: %s", exc)
    return winner_backend, winner_answer


def _record_latency(backend: str, latency_ms: float) -> None:
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
