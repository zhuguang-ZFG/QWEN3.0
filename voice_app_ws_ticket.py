"""One-time tickets for device-app legacy voice WebSocket connections."""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass

TTL_SECONDS = 30
_MAX_TICKETS = 10_000

_lock = threading.Lock()
_tickets: dict[str, "_VoiceAppTicket"] = {}


@dataclass(frozen=True)
class _VoiceAppTicket:
    account_id: str
    expires_at: float


def issue(account_id: str) -> str:
    """Create a single-use ticket bound to *account_id*."""
    ticket = secrets.token_urlsafe(32)
    expires_at = time.time() + TTL_SECONDS
    with _lock:
        _purge_expired(time.time())
        if len(_tickets) >= _MAX_TICKETS:
            _evict_oldest()
        _tickets[ticket] = _VoiceAppTicket(account_id, expires_at)
    return ticket


def peek(ticket: str) -> str | None:
    """Return the bound account id for a valid ticket without consuming it."""
    if not ticket:
        return None
    now = time.time()
    with _lock:
        entry = _tickets.get(ticket)
        _purge_expired(now)
    if entry is None or now > entry.expires_at:
        return None
    return entry.account_id


def consume(ticket: str) -> str | None:
    """Validate and consume a ticket. Returns the bound account id or None."""
    if not ticket:
        return None
    now = time.time()
    with _lock:
        entry = _tickets.pop(ticket, None)
        _purge_expired(now)
    if entry is None or now > entry.expires_at:
        return None
    return entry.account_id


def reset() -> None:
    """Clear ticket store (tests only)."""
    with _lock:
        _tickets.clear()


def _purge_expired(now: float) -> None:
    expired = [ticket for ticket, entry in _tickets.items() if entry.expires_at <= now]
    for ticket in expired:
        del _tickets[ticket]


def _evict_oldest() -> None:
    victims = sorted(_tickets.items(), key=lambda item: item[1].expires_at)
    for ticket, _ in victims[: max(1, len(_tickets) // 4)]:
        _tickets.pop(ticket, None)
