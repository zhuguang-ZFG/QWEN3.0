"""warmup.py — Backend pre-warming to eliminate cold-start latency.

Background: free API backends often have cold starts (container spin-up).
Sending a tiny probe request before real traffic eliminates this.

Usage:
  - Auto-runs on server startup (called from lifespan)
  - Manual: /lima warm
"""
from __future__ import annotations

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor

_log = logging.getLogger(__name__)

# Backends to warm up (fast, commonly used for first responses)
WARMUP_BACKENDS = [
    "longcat_chat", "longcat_lite", "scnet_ds_flash",
    "scnet_qwen30b", "github_gpt4o_mini",
]

WARMUP_PROMPT = "hi"  # Minimal prompt for warmup
WARMUP_MAX_TOKENS = 1
WARMUP_TIMEOUT = 15.0


def warmup_backend(backend: str) -> tuple[str, float, bool]:
    """Send a minimal probe to one backend. Returns (name, latency_ms, ok)."""
    try:
        import http_caller
        t0 = time.time()
        answer = http_caller.call_api(
            backend,
            [{"role": "user", "content": WARMUP_PROMPT}],
            max_tokens=WARMUP_MAX_TOKENS,
            system_prompt="Reply with one word.",
        )
        latency = (time.time() - t0) * 1000
        ok = bool(answer and len(answer.strip()) > 0)
        return backend, latency, ok
    except Exception as e:
        return backend, (time.time() - t0) * 1000, False


def warmup_all(backends: list[str] | None = None, max_workers: int = 3) -> dict:
    """Warm up multiple backends in parallel. Returns timing summary."""
    targets = backends or WARMUP_BACKENDS
    t0 = time.time()
    results = {}

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(warmup_backend, b): b for b in targets}
        for future in futures:
            try:
                name, latency, ok = future.result(timeout=WARMUP_TIMEOUT + 5)
                results[name] = {"latency_ms": round(latency), "ok": ok}
                _log.info("Warmup %s: %.0fms %s", name, latency, "OK" if ok else "FAIL")
            except Exception as exc:
                name = futures[future]
                _log.debug("Warmup %s failed: %s", name, type(exc).__name__)
                results[name] = {"latency_ms": 0, "ok": False}

    total_ms = (time.time() - t0) * 1000
    ok_count = sum(1 for r in results.values() if r["ok"])
    _log.info("Warmup complete: %d/%d OK in %.0fms", ok_count, len(targets), total_ms)

    return {
        "total_ms": round(total_ms),
        "ok": ok_count,
        "total": len(targets),
        "backends": results,
    }


async def warmup_async() -> dict:
    """Async warmup that doesn't block server startup."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, warmup_all)
