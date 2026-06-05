"""Startup registration of all configured backends for health + circuit breaker."""

from __future__ import annotations

import logging

_log = logging.getLogger(__name__)


def bootstrap_runtime_health() -> dict[str, int]:
    """Seed health_tracker and router_circuit_breaker for every registry backend."""
    try:
        from backends_registry import BACKENDS
    except ImportError:
        _log.debug("health bootstrap skipped: backends_registry missing")
        return {"backends": 0, "health_seeded": 0, "cb_seeded": 0}

    names = sorted(BACKENDS.keys())
    if not names:
        return {"backends": 0, "health_seeded": 0, "cb_seeded": 0}

    import health_tracker
    import router_circuit_breaker

    health_seeded = health_tracker.seed_backends(names)
    cb_seeded = router_circuit_breaker.seed_backends(names)
    msg = (
        f"Health bootstrap: {len(names)} backends "
        f"({health_seeded} new health, {cb_seeded} new cb)"
    )
    _log.info(msg)
    print(f"[health-bootstrap] {msg}", flush=True)
    return {
        "backends": len(names),
        "health_seeded": health_seeded,
        "cb_seeded": cb_seeded,
    }
