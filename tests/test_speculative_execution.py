"""Tests for speculative_execution module (AUDIT-8-P8)."""

from unittest.mock import MagicMock, patch

import pytest

import speculative_execution as spec_exec


@pytest.fixture(autouse=True)
def _reset_spec_executor():
    spec_exec._shutdown_shared_executor()
    yield
    spec_exec._shutdown_shared_executor()


def _fake_call_fn(backend: str, _messages: list[dict], _max_tokens: int) -> str:
    return f"{backend} answer long enough"


def test_speculative_call_reuses_shared_executor(monkeypatch):
    """ThreadPoolExecutor should be created once and reused across calls."""
    from concurrent.futures import Future

    monkeypatch.setattr(spec_exec.health_tracker, "record_success", lambda *a, **k: None)
    monkeypatch.setattr(spec_exec.budget_manager, "record_usage", lambda *a, **k: None)

    with patch("speculative_execution.ThreadPoolExecutor") as mock_executor_cls:
        mock_executor = MagicMock()
        mock_executor_cls.return_value = mock_executor

        def _make_future(*args, **kwargs):
            fut = Future()
            fut.set_result("backend1 answer long enough")
            return fut

        mock_executor.submit.side_effect = _make_future

        spec_exec.speculative_call(["b1"], _fake_call_fn, [{"role": "user", "content": "hi"}])
        spec_exec.speculative_call(["b2"], _fake_call_fn, [{"role": "user", "content": "hi"}])

    assert mock_executor_cls.call_count == 1
    assert mock_executor.submit.call_count == 2


def test_speculative_worker_failure_does_not_record_health_failure(monkeypatch):
    """A losing/failing speculative worker must not penalize backend health."""
    monkeypatch.setattr(spec_exec.health_tracker, "record_success", lambda *a, **k: None)
    monkeypatch.setattr(spec_exec.budget_manager, "record_usage", lambda *a, **k: None)
    record_failure_calls = []
    monkeypatch.setattr(spec_exec.health_tracker, "record_failure", lambda *a, **k: record_failure_calls.append((a, k)))

    def failing_call(backend: str, _messages: list[dict], _max_tokens: int) -> str:
        raise RuntimeError("backend down")

    with pytest.raises(RuntimeError, match="All speculative backends failed"):
        spec_exec.speculative_call(["bad"], failing_call, [{"role": "user", "content": "hi"}])

    assert not record_failure_calls
