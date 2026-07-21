"""One-time tickets for device WebSocket connections (/device/v1/ws)."""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass

TTL_SECONDS = 30
_MAX_TICKETS = 10_000

_lock = threading.Lock()
_tickets: dict[str, "_DeviceTicket"] = {}


@dataclass(frozen=True)
class _DeviceTicket:
    device_id: str
    token: str
    expires_at: float


def issue(device_id: str, token: str) -> str:
    ticket = secrets.token_urlsafe(32)
    expires_at = time.time() + TTL_SECONDS
    with _lock:
        _purge_expired(time.time())
        if len(_tickets) >= _MAX_TICKETS:
            _evict_oldest()
        _tickets[ticket] = _DeviceTicket(device_id, token, expires_at)
    return ticket


def consume(ticket: str) -> tuple[str, str] | None:
    if not ticket:
        return None
    now = time.time()
    with _lock:
        entry = _tickets.pop(ticket, None)
        _purge_expired(now)
    if entry is None or now > entry.expires_at:
        return None
    return entry.device_id, entry.token


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
