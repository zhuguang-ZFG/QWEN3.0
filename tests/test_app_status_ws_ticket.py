"""Tests for app_status_ws_ticket peek/consume semantics."""

from __future__ import annotations

import time

import pytest

import app_status_ws_connections
import app_status_ws_ticket


def test_peek_does_not_consume_ticket():
    app_status_ws_ticket.reset()
    ticket = app_status_ws_ticket.issue("dev-1", "a-owner")
    assert app_status_ws_ticket.peek(ticket) == ("dev-1", "a-owner")
    assert app_status_ws_ticket.peek(ticket) == ("dev-1", "a-owner")
    assert app_status_ws_ticket.consume(ticket) == ("dev-1", "a-owner")
    assert app_status_ws_ticket.peek(ticket) is None


def test_peek_unknown_ticket_returns_none():
    app_status_ws_ticket.reset()
    assert app_status_ws_ticket.peek("missing") is None


def test_peek_expired_ticket_returns_none(monkeypatch):
    app_status_ws_ticket.reset()
    ticket = app_status_ws_ticket.issue("dev-1", "a-owner")
    frozen = time.time() + 10_000
    monkeypatch.setattr(app_status_ws_ticket.time, "time", lambda: frozen)
    assert app_status_ws_ticket.peek(ticket) is None
    assert app_status_ws_ticket.consume(ticket) is None


def test_consume_if_rejects_without_burning():
    app_status_ws_ticket.reset()
    ticket = app_status_ws_ticket.issue("dev-1", "a-owner")
    assert app_status_ws_ticket.consume_if(ticket, lambda did, _aid: did == "dev-2") is None
    assert app_status_ws_ticket.peek(ticket) == ("dev-1", "a-owner")
    assert app_status_ws_ticket.consume_if(ticket, lambda did, aid: did == "dev-1" and aid == "a-owner") == (
        "dev-1",
        "a-owner",
    )
    assert app_status_ws_ticket.peek(ticket) is None


@pytest.mark.asyncio
async def test_finalize_preserves_pre_accept_close_1008():
    """Pre-accept close(1008) must not get a blank finalize close (default 1000)."""
    from starlette.websockets import WebSocketState

    from routes.device_app_status_ws import _finalize_status_ws

    app_status_ws_connections.reset()
    closed = {"codes": []}

    class _FakeWs:
        application_state = WebSocketState.CONNECTING

        async def close(self, code: int = 1000, reason: str | None = None):
            closed["codes"].append(code)

    ws = _FakeWs()
    await ws.close(code=1008)
    await _finalize_status_ws(ws, "a-owner", "dev-1")
    assert closed["codes"] == [1008]
