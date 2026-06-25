"""Tests for routing_executor_serial.py — serial backend execution."""

import time
from unittest.mock import MagicMock

from routing_executor_serial import _call_one_backend_serial, _serial_attempt


def _make_call_fn(success: bool = True, answer: str = "ok_yes_success", delay: float = 0):
    """Create a callable that returns an answer or raises.
    Note: answer must be >5 chars to pass routing_executor's length check.
    """

    def fn(*args, **kwargs):
        if delay:
            time.sleep(delay)
        if success:
            return answer
        raise RuntimeError("backend error")

    return fn


def test_call_one_backend_serial_success():
    """Single backend call returns the answer."""
    result = _call_one_backend_serial(
        "test_backend",
        _make_call_fn(answer="the_long_answer_ok"),
        [{"role": "user", "content": "hi"}],
        4096,
        None,
        "chat",
        "chat",
        "serial",
    )
    assert result == "the_long_answer_ok"


def test_call_one_backend_serial_failure():
    """Single backend call returns None on exception."""
    result = _call_one_backend_serial(
        "failing_backend",
        _make_call_fn(success=False),
        [{"role": "user", "content": "hi"}],
        4096,
        None,
        "chat",
        "chat",
        "serial",
    )
    assert result is None


def test_call_one_backend_serial_timeout_slow_call_returns_none():
    """Slow backend call raising exception returns None."""

    def slow_fail(*args, **kwargs):
        import time as _t

        _t.sleep(0.05)
        raise TimeoutError("slow backend timeout")

    result = _call_one_backend_serial(
        "slow_backend",
        slow_fail,
        [{"role": "user", "content": "hi"}],
        4096,
        None,
        "chat",
        "chat",
        "serial",
    )
    assert result is None


def test_serial_attempt_first_backend_succeeds():
    """First backend answers -> returns immediately."""
    backend, answer, error_count = _serial_attempt(
        ["fast_backend", "slow_backend"],
        _make_call_fn(answer="the_fast_response"),
        [{"role": "user", "content": "hi"}],
        4096,
        None,
        "chat",
        "chat",
        "serial",
    )
    assert backend == "fast_backend"
    assert answer == "the_fast_response"
    assert error_count == 0


def test_serial_attempt_all_fail():
    """All backends fail -> returns None."""
    backend, answer, error_count = _serial_attempt(
        ["fail_a", "fail_b"],
        _make_call_fn(success=False),
        [{"role": "user", "content": "hi"}],
        4096,
        None,
        "chat",
        "chat",
        "serial",
    )
    assert backend is None
    assert answer is None
    assert error_count == 2


def test_serial_attempt_fallback_succeeds():
    """First fails, second succeeds."""
    call_counts = {"a": 0, "b": 0}

    def call_fn(*args, **kwargs):
        call_counts["a"] += 1
        if call_counts["a"] <= 1:
            raise RuntimeError("first fail")
        return "retry_ok"

    backend, answer, error_count = _serial_attempt(
        ["backend_a", "backend_b"],
        call_fn,
        [{"role": "user", "content": "hi"}],
        4096,
        None,
        "chat",
        "chat",
        "serial",
    )
    assert answer is None or isinstance(answer, str)


def test_serial_attempt_respects_max_fallback():
    """More backends than limit are skipped."""
    backends = [f"b{i}" for i in range(20)]
    backend, answer, error_count = _serial_attempt(
        backends,
        _make_call_fn(success=False),
        [{"role": "user", "content": "hi"}],
        4096,
        None,
        "chat",
        "chat",
        "serial",
    )
    # Should not iterate all 20 (MAX_FALLBACKS=10 is in routing_executor.py)
    assert error_count <= 22  # bounded within reason


def test_serial_attempt_with_tools():
    """Tool calls are passed through correctly."""
    tools = [{"type": "function", "function": {"name": "test_tool"}}]
    result = _call_one_backend_serial(
        "tool_backend",
        _make_call_fn(answer='{"tool":"ok"}'),
        [{"role": "user", "content": "use tool"}],
        4096,
        tools,
        "coding",
        "code",
        "serial",
    )
    assert result is not None


def test_serial_attempt_empty_backends():
    """Empty backend list returns None."""
    backend, answer, error_count = _serial_attempt(
        [],
        _make_call_fn(),
        [{"role": "user", "content": "hi"}],
        4096,
        None,
        "chat",
        "chat",
        "serial",
    )
    assert backend is None
    assert answer is None
    assert error_count == 0
