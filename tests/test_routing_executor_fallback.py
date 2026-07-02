"""Tests for routing_executor_fallback.py — degraded backend execution."""

import time
import pytest

MOCK_NOW = 2_000_000_000.0  # fixed deterministic timestamp for stable tests

from routing_executor.fallback import (
    _select_fallback_candidates,
    _serial_fallback_attempt,
    _fallback_phase,
)


def _make_call_fn(success=True, answer="fallback_ok", delay=0):
    def fn(*args, **kwargs):
        if delay:
            time.sleep(delay)
        if success:
            return answer
        raise RuntimeError("backend error")

    return fn


def test_select_fallback_candidates_returns_up_to_three():
    """Returns at most 3 candidates."""
    candidates = _select_fallback_candidates(["a", "b", "c", "d", "e"])
    assert len(candidates) <= 3
    assert all(c in ("a", "b", "c", "d", "e") for c in candidates)


def test_select_fallback_candidates_less_than_three():
    """Returns all when fewer than 3."""
    candidates = _select_fallback_candidates(["a"])
    assert candidates == ["a"]


def test_select_fallback_candidates_empty():
    """Empty input returns empty list."""
    assert _select_fallback_candidates([]) == []


def test_serial_fallback_attempt_success():
    """Fallback attempt succeeds on first candidate."""
    result = _serial_fallback_attempt(
        ["f1", "f2"],
        _make_call_fn(answer="fallback_ans"),
        [{"role": "user", "content": "hi"}],
        4096,
        None,
        "chat",
        "chat",
        MOCK_NOW,
    )
    assert result is not None
    backend, answer = result
    assert answer == "fallback_ans"


def test_serial_fallback_attempt_all_fail():
    """All fallback candidates fail -> returns None."""
    result = _serial_fallback_attempt(
        ["fail1", "fail2"],
        _make_call_fn(success=False),
        [{"role": "user", "content": "hi"}],
        4096,
        None,
        "chat",
        "chat",
        MOCK_NOW,
    )
    assert result is None


def test_serial_fallback_attempt_empty():
    """Empty candidates -> returns None."""
    result = _serial_fallback_attempt(
        [],
        _make_call_fn(),
        [{"role": "user", "content": "hi"}],
        4096,
        None,
        "chat",
        "chat",
        MOCK_NOW,
    )
    assert result is None


def test_fallback_phase_prefers_parallel_for_multi():
    """When >=2 candidates, parallel is preferred."""
    result = _fallback_phase(
        ["a", "b", "c"],
        _make_call_fn(answer="phase_ok"),
        [{"role": "user", "content": "hi"}],
        4096,
        None,
        "chat",
        "chat",
        MOCK_NOW,
    )
    assert result is not None


def test_fallback_phase_single_candidate():
    """Single candidate falls back to serial attempt."""
    result = _fallback_phase(
        ["only_one"],
        _make_call_fn(answer="sole_result_long"),
        [{"role": "user", "content": "hi"}],
        4096,
        None,
        "chat",
        "chat",
        MOCK_NOW,
    )
    assert result == ("only_one", "sole_result_long")


def test_fallback_phase_empty():
    """Empty backends -> returns None."""
    result = _fallback_phase(
        [],
        _make_call_fn(),
        [{"role": "user", "content": "hi"}],
        4096,
        None,
        "chat",
        "chat",
        MOCK_NOW,
    )
    assert result is None


def test_fallback_phase_all_fail():
    """All options exhausted -> returns None."""
    result = _fallback_phase(
        ["bad1", "bad2", "bad3"],
        _make_call_fn(success=False),
        [{"role": "user", "content": "hi"}],
        4096,
        None,
        "chat",
        "chat",
        MOCK_NOW,
    )
    assert result is None


@pytest.fixture(autouse=True)
def fixed_time(monkeypatch):
    monkeypatch.setattr(time, "time", lambda: MOCK_NOW)
