"""Shared WebSocket helpers for routes."""

from __future__ import annotations

from fastapi import WebSocket


def _client_ip_from_websocket(websocket: WebSocket) -> str:
    """Best-effort client IP extraction from WS scope/headers."""
    scope = websocket.scope
    client = scope.get("client")
    if isinstance(client, (list, tuple)) and len(client) >= 1:
        return str(client[0])
    forwarded = websocket.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return websocket.headers.get("x-real-ip", "127.0.0.1")
