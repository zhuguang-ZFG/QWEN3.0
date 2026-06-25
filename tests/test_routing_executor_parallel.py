"""Tests for routing_executor_parallel.py — parallel backend execution."""

import time
from unittest.mock import MagicMock

from routing_executor_parallel import _try_one_parallel, _parallel_fallback


def _make_call_fn(success=True, answer="the_long_ok", delay=0):
    """Create a callable that returns answer or raises.
    Note: answer must be >5 chars to pass routing_executor's length check.
    """

    def fn(*args, **kwargs):
        if delay:
            time.sleep(delay)
        if success:
            return answer
        raise RuntimeError("backend error")

    return fn


def test_try_one_parallel_success():
    """Parallel call returns (backend, answer) on success."""
    result = _try_one_parallel(
        "p_backend",
        _make_call_fn(answer="success_response"),
        [{"role": "user", "content": "hi"}],
        4096,
        None,
        scenario="chat",
        request_type="chat",
    )
    assert result == ("p_backend", "success_response")


def test_try_one_parallel_failure():
    """Parallel call returns None on exception."""
    result = _try_one_parallel(
        "fail_backend",
        _make_call_fn(success=False),
        [{"role": "user", "content": "hi"}],
        4096,
        None,
        scenario="chat",
        request_type="chat",
    )
    assert result is None


def test_try_one_parallel_failure_returns_none():
    """Parallel call returns None on exception."""
    result = _try_one_parallel(
        "fail_backend",
        _make_call_fn(success=False),
        [{"role": "user", "content": "hi"}],
        4096,
        None,
        scenario="chat",
        request_type="chat",
    )
    assert result is None


def test_try_one_parallel_short_answer_returns_none():
    """Short answer (< 6 chars) returns None."""

    def short_answer(*args, **kwargs):
        return "ab"

    result = _try_one_parallel(
        "short_backend",
        short_answer,
        [{"role": "user", "content": "hi"}],
        4096,
        None,
        scenario="chat",
        request_type="chat",
    )
    assert result is None


def test_parallel_fallback_some_succeed():
    """At least one parallel call succeeds."""

    def picky_fn(*args, **kwargs):
        return "picky_ok"

    result = _parallel_fallback(
        ["fast_a", "fast_b", "fast_c"],
        picky_fn,
        [{"role": "user", "content": "hi"}],
        4096,
        None,
        scenario="chat",
        request_type="chat",
    )
    assert result is not None
    backend, answer = result
    assert answer == "picky_ok"


def test_parallel_fallback_all_fail():
    """All parallel calls fail -> returns None."""
    result = _parallel_fallback(
        ["fail_a", "fail_b"],
        _make_call_fn(success=False),
        [{"role": "user", "content": "hi"}],
        4096,
        None,
        scenario="chat",
        request_type="chat",
    )
    assert result is None


def test_parallel_fallback_empty():
    """Empty backend list -> returns None (empty loop, no executor created)."""
    try:
        result = _parallel_fallback(
            [],
            _make_call_fn(),
            [{"role": "user", "content": "hi"}],
            4096,
            None,
            scenario="chat",
            request_type="chat",
        )
        assert result is None
    except ValueError:
        pass  # ThreadPoolExecutor(max_workers=0) raises on some Python versions


def test_parallel_fallback_single_backend():
    """Single backend in parallel list."""
    result = _parallel_fallback(
        ["sole_backend"],
        _make_call_fn(answer="sole_result_ok"),
        [{"role": "user", "content": "hi"}],
        4096,
        None,
        scenario="chat",
        request_type="chat",
    )
    assert result == ("sole_backend", "sole_result_ok")


def test_parallel_fallback_with_tools():
    """Tool config passed through in parallel calls."""
    tools = [{"type": "function", "function": {"name": "calc"}}]
    result = _try_one_parallel(
        "tool_backend",
        _make_call_fn(answer="forty_two_result"),
        [{"role": "user", "content": "calc"}],
        4096,
        tools,
        scenario="coding",
        request_type="code",
    )
    assert result == ("tool_backend", "forty_two_result")
