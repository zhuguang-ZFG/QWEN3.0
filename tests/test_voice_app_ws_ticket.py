"""Tests for voice_app_ws_ticket peek/consume semantics."""

from __future__ import annotations

import voice_app_ws_ticket


def test_peek_does_not_consume_ticket():
    voice_app_ws_ticket.reset()
    ticket = voice_app_ws_ticket.issue("a-owner")
    assert voice_app_ws_ticket.peek(ticket) == "a-owner"
    assert voice_app_ws_ticket.peek(ticket) == "a-owner"
    assert voice_app_ws_ticket.consume(ticket) == "a-owner"
    assert voice_app_ws_ticket.peek(ticket) is None


def test_peek_unknown_ticket_returns_none():
    voice_app_ws_ticket.reset()
    assert voice_app_ws_ticket.peek("missing") is None
