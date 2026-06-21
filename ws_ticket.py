"""One-time WebSocket connection tickets (avoid long-lived tokens in query strings)."""

from __future__ import annotations

import secrets
import threading
import time

TTL_SECONDS = 30
_MAX_TICKETS = 10_000

_lock = threading.Lock()
_tickets: dict[str, float] = {}


def issue() -> str:
    """Create a single-use ticket valid for TTL_SECONDS."""
    ticket = secrets.token_urlsafe(32)
    expires_at = time.time() + TTL_SECONDS
    with _lock:
        _purge_expired(time.time())
        if len(_tickets) >= _MAX_TICKETS:
            _evict_oldest()
        _tickets[ticket] = expires_at
    return ticket


def consume(ticket: str) -> bool:
    """Validate and consume a ticket. Returns False when missing or expired."""
    if not ticket:
        return False
    now = time.time()
    with _lock:
        expires_at = _tickets.pop(ticket, None)
        _purge_expired(now)
    return expires_at is not None and now <= expires_at


def reset() -> None:
    """Clear ticket store (tests only)."""
    with _lock:
        _tickets.clear()


def _purge_expired(now: float) -> None:
    expired = [ticket for ticket, expires_at in _tickets.items() if expires_at <= now]
    for ticket in expired:
        del _tickets[ticket]


def _evict_oldest() -> None:
    victims = sorted(_tickets.items(), key=lambda item: item[1])
    for ticket, _ in victims[: max(1, len(_tickets) // 4)]:
        _tickets.pop(ticket, None)
