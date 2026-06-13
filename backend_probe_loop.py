"""Backend Probe Loop — periodic health probing for all configured backends.

Runs as a background thread, probing backends in batches every N minutes.
Updates health_tracker and backend_profile with probe results.
"""

from __future__ import annotations

import concurrent.futures
import logging
import os
import threading
import time

logger = logging.getLogger(__name__)

# Probe interval: 5 minutes between batches
PROBE_INTERVAL = int(os.environ.get("LIMA_PROBE_INTERVAL", 300))
OPERATOR_PROBE_TIMEOUT = float(os.environ.get("LIMA_OPERATOR_PROBE_TIMEOUT", 25))
OPERATOR_PROBE_WORKERS = int(os.environ.get("LIMA_OPERATOR_PROBE_WORKERS", 4))
# Number of batches (full cycle = PROBE_INTERVAL * NUM_BATCHES)
NUM_BATCHES = 4

_running = False
_thread: threading.Thread | None = None
_operator_probe_executor = concurrent.futures.ThreadPoolExecutor(
    max_workers=max(1, OPERATOR_PROBE_WORKERS),
    thread_name_prefix="operator-probe",
)


def start_probe_loop() -> None:
    """Start the background probe loop thread."""
    global _running, _thread
    if _running:
        return
    _running = True
    _thread = threading.Thread(target=_probe_loop, daemon=True, name="probe-loop")
    _thread.start()
    logger.info("Backend probe loop started (interval=%ds, batches=%d)", PROBE_INTERVAL, NUM_BATCHES)


def stop_probe_loop() -> None:
    """Stop the background probe loop."""
    global _running
    _running = False
    logger.info("Backend probe loop stopped")


def probe_backend(backend: str, *, ignore_cooldown: bool = False) -> dict:
    """Probe a single backend. Returns probe result dict."""
    try:
        from backends import BACKENDS
        import http_caller

        cfg = BACKENDS.get(backend, {})
        if not cfg:
            return {"backend": backend, "status": "unknown", "error": "not configured"}

        # Quick connectivity probe
        t0 = time.time()
        try:
            result = http_caller.call_api(
                backend,
                [{"role": "user", "content": "hi"}],
                5,
                ignore_cooldown=ignore_cooldown,
            )
            latency_ms = int((time.time() - t0) * 1000)
            if result and len(result.strip()) > 0:
                return {
                    "backend": backend,
                    "status": "healthy",
                    "latency_ms": latency_ms,
                    "response_len": len(result),
                }
            else:
                return {"backend": backend, "status": "empty", "latency_ms": latency_ms}
        except Exception as exc:
            latency_ms = int((time.time() - t0) * 1000)
            error_class = _classify_error(str(exc))
            return {
                "backend": backend,
                "status": "failed",
                "latency_ms": latency_ms,
                "error": str(exc)[:100],
                "error_class": error_class,
            }
    except ImportError:
        return {"backend": backend, "status": "error", "error": "http_caller not available"}


def probe_batch(backends: list[str]) -> list[dict]:
    """Probe a batch of backends."""
    results = []
    for backend in backends:
        result = probe_backend(backend)
        results.append(result)
        # Brief pause between probes to avoid rate limiting
        time.sleep(0.5)
    return results


def record_probe_result(result: dict) -> bool:
    """Persist a probe result into health/profile/telemetry stores."""
    backend = str(result.get("backend", ""))
    if not backend:
        return False
    status = str(result.get("status", "unknown"))
    success = status == "healthy"
    latency_ms = int(result.get("latency_ms", 0) or 0)

    recorded = False
    try:
        import health_tracker

        if success:
            health_tracker.record_success(backend, latency_ms)
        elif status in ("failed", "empty"):
            health_tracker.record_failure(
                backend,
                error_code=result.get("error_code"),
                error_text=str(result.get("error", "")),
            )
        recorded = True
    except ImportError as exc:
        logger.warning("health_tracker unavailable; probe health not recorded: %s", exc)

    try:
        import backend_profile

        backend_profile.record_request(
            backend,
            latency_ms,
            success=success,
            scenario="probe",
            response_len=int(result.get("response_len", 0) or 0),
        )
        recorded = True
    except ImportError as exc:
        logger.warning("backend_profile unavailable; probe profile not recorded: %s", exc)

    try:
        from observability.backend_telemetry import record_backend_attempt

        record_backend_attempt(
            backend=backend,
            scenario="probe",
            request_type="operator_probe",
            success=success,
            latency_ms=latency_ms,
            status_code=result.get("error_code"),
            error=result.get("error"),
            response_empty=(status == "empty"),
            phase="operator_probe",
            attempt="manual",
        )
        recorded = True
    except ImportError as exc:
        logger.warning("backend telemetry unavailable; probe attempt not recorded: %s", exc)
    return recorded


def _probe_backend_with_timeout(
    backend: str,
    *,
    ignore_cooldown: bool = False,
    timeout_sec: float,
) -> dict:
    started = time.time()
    future = _operator_probe_executor.submit(
        probe_backend,
        backend,
        ignore_cooldown=ignore_cooldown,
    )
    try:
        return future.result(timeout=timeout_sec)
    except concurrent.futures.TimeoutError:
        future.cancel()
        latency_ms = int((time.time() - started) * 1000)
        return {
            "backend": backend,
            "status": "failed",
            "latency_ms": latency_ms,
            "error": f"operator probe timed out after {timeout_sec:g}s",
            "error_class": "timeout",
            "timed_out": True,
        }


def probe_and_record_backend(
    backend: str,
    *,
    ignore_cooldown: bool = False,
    timeout_sec: float | None = None,
) -> dict:
    """Probe a backend once and persist the evidence for operator recovery."""
    timeout = OPERATOR_PROBE_TIMEOUT if timeout_sec is None else timeout_sec
    if timeout > 0:
        result = _probe_backend_with_timeout(
            backend,
            ignore_cooldown=ignore_cooldown,
            timeout_sec=timeout,
        )
    else:
        result = probe_backend(backend, ignore_cooldown=ignore_cooldown)
    result["recorded"] = record_probe_result(result)
    return result


def get_probe_schedule() -> list[list[str]]:
    """Generate probe batches from all configured backends."""
    try:
        from backends import BACKENDS
    except ImportError:
        return []

    all_backends = list(BACKENDS.keys())
    # Shuffle to spread load
    import random
    random.shuffle(all_backends)

    batch_size = max(1, len(all_backends) // NUM_BATCHES)
    batches = []
    for i in range(0, len(all_backends), batch_size):
        batches.append(all_backends[i:i + batch_size])
    return batches


def _classify_error(error_msg: str) -> str:
    """Classify error type from message."""
    msg = error_msg.lower()
    if "401" in msg or "unauthorized" in msg or "invalid_api_key" in msg:
        return "auth_error"
    if "429" in msg or "rate" in msg or "too many" in msg:
        return "rate_limited"
    if "timeout" in msg or "timed out" in msg:
        return "timeout"
    if "connection" in msg or "network" in msg or "dns" in msg:
        return "network_error"
    return "provider_error"


def _probe_loop() -> None:
    """Background probe loop."""
    global _running
    batch_index = 0

    while _running:
        try:
            schedule = get_probe_schedule()
            if not schedule:
                time.sleep(PROBE_INTERVAL)
                continue

            batch = schedule[batch_index % len(schedule)]
            logger.info("Probing batch %d/%d (%d backends)", batch_index + 1, len(schedule), len(batch))

            results = probe_batch(batch)

            # Update health tracker and backend profile
            for result in results:
                record_probe_result(result)

            healthy = sum(1 for r in results if r.get("status") == "healthy")
            logger.info("Probe batch %d complete: %d/%d healthy", batch_index + 1, healthy, len(results))

            batch_index += 1
            time.sleep(PROBE_INTERVAL)

        except Exception as exc:
            logger.warning("Probe loop error: %s", exc)
            time.sleep(PROBE_INTERVAL)
