"""Thread-safe in-memory storage for probe ingress events (Phase 1)."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone

_probes: dict[str, dict] = {}
_lock = threading.Lock()

# Heuristic: redact metadata fields whose names contain secret-bearing fragments.
# We intentionally err on the side of over-redaction to avoid leaking credentials
# in probe metadata; benign keys such as "monkey" or "author" are preserved.
_SENSITIVE_KEY_FRAGMENTS = frozenset(("token", "secret", "password", "credential", "api_key", "auth_token", "_key"))


def _is_sensitive_key(key: str) -> bool:
    """Return True when *key* indicates a secret-bearing field."""
    lowered = key.lower()
    return any(fragment in lowered for fragment in _SENSITIVE_KEY_FRAGMENTS)


def _sanitize_metadata(value: object) -> object:
    """Keep only primitive, non-secret metadata values."""
    if isinstance(value, dict):
        return {k: _sanitize_metadata(v) for k, v in value.items() if isinstance(k, str) and not _is_sensitive_key(k)}
    if isinstance(value, list):
        return [_sanitize_metadata(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def record_probe_event(
    source: str,
    provider: str,
    status: str,
    latency_ms: float,
    price_tier: str = "",
    checked_at: str = "",
    metadata: dict | None = None,
) -> None:
    """Store or overwrite the latest probe event for a (source, provider) pair."""
    key = f"{source}:{provider}"
    entry = {
        "source": source,
        "provider": provider,
        "status": status,
        "latency_ms": float(latency_ms),
        "price_tier": price_tier,
        "checked_at": checked_at,
        "metadata": _sanitize_metadata(metadata or {}),
        "recorded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    with _lock:
        _probes[key] = entry


def get_probe_snapshot(source: str | None = None) -> dict:
    """Return probe entries, optionally filtered by *source*."""
    with _lock:
        items = list(_probes.values())
    if source is not None:
        items = [item for item in items if item.get("source") == source]
    return {"probes": items, "count": len(items)}


def reset_probe_state() -> None:
    """Clear all stored probe events. Intended for tests only."""
    with _lock:
        _probes.clear()
    logging.debug("probe_state: reset")
