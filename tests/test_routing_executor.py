"""Tests for routing_executor.py — high-level execute orchestration (P1-5)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from routing_executor import MAX_FALLBACKS, MAX_FALLBACKS_TOOLS, execute


@pytest.fixture
def call_fn():
    return MagicMock(return_value="the_long_answer")


def test_execute_first_backend_succeeds(monkeypatch, call_fn):
    monkeypatch.setattr(
        "routing_executor._serial_attempt",
        lambda *a, **kw: ("first", "serial_answer", 0),
    )
    monkeypatch.setattr("routing_executor._fallback_phase", lambda *a, **kw: None)
    backend, answer, errors = execute(["first"], call_fn, [])
    assert backend == "first"
    assert answer == "serial_answer"
    assert errors == 0


def test_execute_falls_back_when_serial_fails(monkeypatch, call_fn):
    monkeypatch.setattr(
        "routing_executor._serial_attempt",
        lambda *a, **kw: (None, None, 1),
    )
    monkeypatch.setattr(
        "routing_executor._fallback_phase",
        lambda *a, **kw: ("fallback", "fallback_answer"),
    )
    backend, answer, errors = execute(["a", "b"], call_fn, [])
    assert backend == "fallback"
    assert answer == "fallback_answer"
    assert errors == 1


def test_execute_exhausted_when_all_fail(monkeypatch, call_fn):
    monkeypatch.setattr(
        "routing_executor._serial_attempt",
        lambda *a, **kw: (None, None, 2),
    )
    monkeypatch.setattr("routing_executor._fallback_phase", lambda *a, **kw: None)
    backend, answer, errors = execute(["a"], call_fn, [])
    assert backend == "exhausted"
    assert answer == ""
    assert errors == 2


def test_execute_limits_backends_without_tools(monkeypatch, call_fn):
    captured: list[str] = []

    def fake_serial(backends, *args, **kwargs):
        captured.extend(backends)
        return ("ok", "answer", 0)

    monkeypatch.setattr("routing_executor._serial_attempt", fake_serial)
    execute([f"b{i}" for i in range(MAX_FALLBACKS + 10)], call_fn, [])
    assert len(captured) == MAX_FALLBACKS


def test_execute_uses_higher_limit_with_tools(monkeypatch, call_fn):
    captured: list[str] = []

    def fake_serial(backends, *args, **kwargs):
        captured.extend(backends)
        return ("ok", "answer", 0)

    monkeypatch.setattr("routing_executor._serial_attempt", fake_serial)
    tools = [{"type": "function", "function": {"name": "test_tool"}}]
    execute([f"b{i}" for i in range(MAX_FALLBACKS_TOOLS + 10)], call_fn, [], tools=tools)
    assert len(captured) == MAX_FALLBACKS_TOOLS
