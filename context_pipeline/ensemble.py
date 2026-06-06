"""Ensemble module — parallel multi-backend calls for quality optimization.

Based on all-agentic-architectures Ensemble pattern:
- For critical requests (IDE coding), send to 2-3 backends in parallel
- Take the fastest successful response (race strategy)
- Or compare responses and pick the best (quality strategy)
- Reduces latency and improves reliability
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass


@dataclass
class EnsembleResult:
    """Result of an ensemble call."""

    winner_backend: str
    response: dict
    latency_ms: int
    candidates_tried: int
    candidates_succeeded: int
    strategy: str


@dataclass
class EnsembleCandidate:
    """A single backend candidate in an ensemble call."""

    backend: str
    response: dict | None = None
    latency_ms: int = 0
    success: bool = False
    error: str = ""


async def ensemble_race(
    backends: list[str],
    call_fn: Callable[[str], Awaitable[dict]],
    timeout_ms: int = 15000,
) -> EnsembleResult:
    """Race strategy: first successful response wins.

    Sends request to all backends in parallel, returns the first
    successful response. Cancels remaining tasks.
    """
    if not backends:
        return EnsembleResult(
            winner_backend="",
            response={"error": "no backends"},
            latency_ms=0,
            candidates_tried=0,
            candidates_succeeded=0,
            strategy="race",
        )

    start = time.time()
    candidates: list[EnsembleCandidate] = []

    async def _call(backend: str) -> EnsembleCandidate:
        t0 = time.time()
        try:
            resp = await call_fn(backend)
            ms = int((time.time() - t0) * 1000)
            return EnsembleCandidate(
                backend=backend, response=resp,
                latency_ms=ms, success=True,
            )
        except Exception as e:
            ms = int((time.time() - t0) * 1000)
            return EnsembleCandidate(
                backend=backend, latency_ms=ms,
                success=False, error=str(e)[:100],
            )

    timeout_s = timeout_ms / 1000.0
    tasks = [asyncio.create_task(_call(b)) for b in backends]

    winner = None
    for coro in asyncio.as_completed(tasks, timeout=timeout_s):
        try:
            candidate = await coro
            candidates.append(candidate)
            if candidate.success and winner is None:
                winner = candidate
                break
        except asyncio.TimeoutError:
            break

    for t in tasks:
        if not t.done():
            t.cancel()

    total_ms = int((time.time() - start) * 1000)

    if winner:
        return EnsembleResult(
            winner_backend=winner.backend,
            response=winner.response or {},
            latency_ms=winner.latency_ms,
            candidates_tried=len(backends),
            candidates_succeeded=sum(1 for c in candidates if c.success),
            strategy="race",
        )

    return EnsembleResult(
        winner_backend="",
        response={"error": "all backends failed"},
        latency_ms=total_ms,
        candidates_tried=len(backends),
        candidates_succeeded=0,
        strategy="race",
    )


def should_use_ensemble(scenario: str, ide: str) -> bool:
    """Decide whether to use ensemble for this request.

    Ensemble is expensive (multiple backend calls), so only use for:
    - IDE coding requests (high value, quality matters)
    - When multiple backends are available
    """
    return scenario == "coding" and bool(ide)


def select_ensemble_backends(
    primary: str,
    fallback_pool: list[str],
    max_candidates: int = 3,
) -> list[str]:
    """Select backends for ensemble call.

    Always includes the primary, plus up to max_candidates-1 from fallback pool.
    """
    candidates = [primary]
    for b in fallback_pool:
        if b != primary and len(candidates) < max_candidates:
            candidates.append(b)
    return candidates
