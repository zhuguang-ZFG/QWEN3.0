"""Token Health — validate and monitor API key/token health.

Periodically checks each backend's authentication status.
Expired tokens are logged and can be refreshed via token-sync.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import time

logger = logging.getLogger(__name__)
_log = logger

DB_PATH = os.environ.get("LIMA_TOKEN_HEALTH_DB", "data/token_health.db")


def check_token(backend: str) -> dict:
    """Check if a backend's token is valid. Returns health status."""
    try:
        from backends_registry import BACKENDS
        import http_caller

        cfg = BACKENDS.get(backend, {})
        if not cfg:
            return {"backend": backend, "status": "unknown", "error": "not configured"}

        # Skip backends without keys (free APIs)
        key = cfg.get("key", "")
        if not key or key == "none":
            return {"backend": backend, "status": "no_key_needed", "ok": True}

        # Resolve env var
        if key.startswith("$"):
            key = os.environ.get(key.lstrip("$"), "")
            if not key:
                return {"backend": backend, "status": "key_not_set", "ok": False}

        # Try a minimal request
        try:
            result = http_caller.call_api(
                backend,
                [{"role": "user", "content": "hi"}],
                3,
            )
            if result and len(result.strip()) > 0:
                return {"backend": backend, "status": "valid", "ok": True}
            return {"backend": backend, "status": "empty_response", "ok": False}
        except Exception as exc:
            error_msg = str(exc).lower()
            if "401" in error_msg or "unauthorized" in error_msg or "invalid_api_key" in error_msg:
                return {"backend": backend, "status": "expired", "ok": False, "error": str(exc)[:100]}
            if "429" in error_msg or "rate" in error_msg:
                return {"backend": backend, "status": "rate_limited", "ok": True}
            return {"backend": backend, "status": "error", "ok": False, "error": str(exc)[:100]}

    except ImportError:
        return {"backend": backend, "status": "error", "ok": False, "error": "http_caller not available"}


def check_all_tokens() -> list[dict]:
    """Check tokens for all configured backends."""
    try:
        from backends_registry import BACKENDS
    except ImportError:
        return []

    results = []
    for name in BACKENDS:
        cfg = BACKENDS[name]
        key = cfg.get("key", "")
        if not key or key == "none":
            continue  # Skip free APIs
        result = check_token(name)
        results.append(result)
    return results


def get_expired_tokens() -> list[dict]:
    """Get all backends with expired tokens."""
    results = check_all_tokens()
    return [r for r in results if r.get("status") == "expired"]


def save_token_status(results: list[dict]) -> None:
    """Save token check results to SQLite."""
    conn = None
    try:
        os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
        conn = sqlite3.connect(DB_PATH, timeout=5)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS token_health (
                backend TEXT PRIMARY KEY,
                status TEXT,
                checked_at REAL,
                error TEXT
            )
        """)
        for r in results:
            conn.execute(
                "INSERT OR REPLACE INTO token_health VALUES (?, ?, ?, ?)",
                (r["backend"], r.get("status", "unknown"), time.time(), r.get("error", "")),
            )
        conn.commit()
    except Exception as exc:
        logger.warning("Failed to save token health: %s", exc)
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception as exc:
                logger.warning("Failed to close DB connection in save_token_status: %s", exc)


def alert_expired_tokens() -> None:
    """Log expired tokens for operator follow-up."""
    expired = get_expired_tokens()
    if not expired:
        return

    names = [r["backend"] for r in expired]
    message = f"Token expired: {', '.join(names[:5])}"
    if len(names) > 5:
        message += f" (+{len(names) - 5} more)"

    for r in expired:
        logger.warning("token expired backend=%s", r["backend"])

    logger.warning("Expired tokens: %s", message)
