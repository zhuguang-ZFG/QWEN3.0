"""One-time tickets for device-app status WebSocket connections."""

from __future__ import annotations

import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

TTL_SECONDS = 30
_MAX_TICKETS = 10_000

_lock = threading.Lock()
_tickets: dict[str, "_AppStatusTicket"] = {}


@dataclass(frozen=True)
class _AppStatusTicket:
    device_id: str
    account_id: str
    expires_at: float


def issue(device_id: str, account_id: str) -> str:
    ticket = secrets.token_urlsafe(32)
    expires_at = time.time() + TTL_SECONDS
    with _lock:
        _purge_expired(time.time())
        if len(_tickets) >= _MAX_TICKETS:
            _evict_oldest()
        _tickets[ticket] = _AppStatusTicket(device_id, account_id, expires_at)
    return ticket


def peek(ticket: str) -> tuple[str, str] | None:
    """Return (device_id, account_id) for a valid ticket without consuming it."""
    if not ticket:
        return None
    now = time.time()
    with _lock:
        _purge_expired(now)
        entry = _tickets.get(ticket)
    if entry is None or now > entry.expires_at:
        return None
    return entry.device_id, entry.account_id


def consume(ticket: str) -> tuple[str, str] | None:
    if not ticket:
        return None
    now = time.time()
    with _lock:
        _purge_expired(now)
        entry = _tickets.pop(ticket, None)
    if entry is None or now > entry.expires_at:
        return None
    return entry.device_id, entry.account_id


def consume_if(
    ticket: str,
    predicate: Callable[[str, str], bool],
) -> tuple[str, str] | None:
    """Consume only when predicate(device_id, account_id) is truthy."""
    if not ticket:
        return None
    now = time.time()
    with _lock:
        _purge_expired(now)
        entry = _tickets.get(ticket)
        if entry is None or now > entry.expires_at:
            return None
        if not predicate(entry.device_id, entry.account_id):
            return None
        _tickets.pop(ticket, None)
    return entry.device_id, entry.account_id


def reset() -> None:
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
