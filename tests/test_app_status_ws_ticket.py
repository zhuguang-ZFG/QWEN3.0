"""Tests for app_status_ws_ticket peek/consume semantics."""

from __future__ import annotations

import time

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
