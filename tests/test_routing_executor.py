"""Tests for routing_executor — execute, fallback, error code extraction."""

import sys
import pytest
from unittest.mock import MagicMock, patch


# ── extract_error_code ──────────────────────────────────────────────────────
class TestExtractErrorCode:
    def test_status_code_attr(self):
        from routing_executor import extract_error_code

        e = Exception("boom")
        e.status_code = 429
        assert extract_error_code(e) == 429

    def test_code_attr(self):
        from routing_executor import extract_error_code

        e = Exception("boom")
        e.code = 401
        assert extract_error_code(e) == 401

    def test_string_429(self):
        from routing_executor import extract_error_code

        assert extract_error_code(Exception("rate limit 429 exceeded")) == 429

    def test_string_403(self):
        from routing_executor import extract_error_code

        assert extract_error_code(Exception("forbidden 403")) == 403

    def test_no_code(self):
        from routing_executor import extract_error_code

        assert extract_error_code(Exception("unknown")) is None


# ── Helper: mock routing_engine module ──────────────────────────────────────
def _make_mock_re(health_cooled=False, budget_available=False):
    """Create a mock routing_engine module for execute() tests."""
    mock_re = MagicMock()
    mock_re.health_tracker.is_cooled_down.return_value = health_cooled
    mock_re.health_tracker.record_success = MagicMock()
    mock_re.health_tracker.record_failure = MagicMock()
    mock_re.health_tracker.detect_and_reset_mass_failure = MagicMock()
    mock_re.budget_manager.record_usage = MagicMock()
    mock_re.budget_manager.is_budget_available.return_value = budget_available
    return mock_re


def _run_execute(mock_re, backends, call_fn, **kwargs):
    """Run execute() with routing_engine mocked via sys.modules."""
    # opencode_retry_policy is also imported inside execute()
    mock_retry = MagicMock()
    mock_retry.is_retryable_error = MagicMock(return_value=False)
    with patch.dict(sys.modules, {
        "routing_engine": mock_re,
        "opencode_retry_policy": mock_retry,
    }):
        from routing_executor import execute
        return execute(backends, call_fn, **kwargs)


# ── execute — happy path ────────────────────────────────────────────────────
class TestExecuteHappyPath:
    def test_first_backend_succeeds(self):
        mock_re = _make_mock_re()
        call_fn = MagicMock(return_value="Hello world")
        backend, answer, errors = _run_execute(
            mock_re, ["backend_a", "backend_b"], call_fn,
            messages=[{"role": "user", "content": "hi"}],
        )
        assert backend == "backend_a"
        assert answer == "Hello world"
        assert errors == 0
        mock_re.health_tracker.record_success.assert_called_once()

    def test_skip_cooled_down_backend(self):
        mock_re = _make_mock_re()
        mock_re.health_tracker.is_cooled_down.side_effect = [True, False]
        call_fn = MagicMock(return_value="answer")
        backend, answer, errors = _run_execute(
            mock_re, ["cold_backend", "warm_backend"], call_fn,
            messages=[{"role": "user", "content": "test"}],
        )
        assert backend == "warm_backend"
        assert errors == 1

    def test_empty_answer_triggers_fallback(self):
        mock_re = _make_mock_re()
        call_fn = MagicMock(side_effect=["", "real answer"])
        backend, answer, errors = _run_execute(
            mock_re, ["bad_backend", "good_backend"], call_fn,
            messages=[{"role": "user", "content": "hi"}],
        )
        assert backend == "good_backend"
        assert answer == "real answer"
        assert errors == 1


# ── execute — overflow propagation ──────────────────────────────────────────
class TestExecuteOverflow:
    def test_overflow_stops_fallback(self):
        mock_re = _make_mock_re()
        overflow_err = Exception("context too long")
        overflow_err.is_overflow = True
        call_fn = MagicMock(side_effect=overflow_err)
        with pytest.raises(Exception, match="context too long"):
            _run_execute(
                mock_re, ["b1", "b2"], call_fn,
                messages=[{"role": "user", "content": "big"}],
            )
        assert call_fn.call_count == 1


# ── execute — exhausted ─────────────────────────────────────────────────────
class TestExecuteExhausted:
    def test_all_backends_fail(self):
        mock_re = _make_mock_re()
        call_fn = MagicMock(side_effect=Exception("fail"))
        backend, answer, errors = _run_execute(
            mock_re, ["b1"], call_fn,
            messages=[{"role": "user", "content": "test"}],
        )
        assert backend == "exhausted"
        assert answer == ""


# ── execute — tools mode ────────────────────────────────────────────────────
class TestExecuteTools:
    def test_tools_passed_to_call_fn(self):
        mock_re = _make_mock_re()
        call_fn = MagicMock(return_value="tool result")
        tools = [{"type": "function", "function": {"name": "test"}}]
        backend, answer, errors = _run_execute(
            mock_re, ["b1"], call_fn,
            messages=[{"role": "user", "content": "hi"}],
            tools=tools,
        )
        assert backend == "b1"
        assert answer == "tool result"
        _, kwargs = call_fn.call_args
        assert kwargs.get("tools") == tools


# ── parallel_fallback ───────────────────────────────────────────────────────
class TestParallelFallback:
    def test_first_valid_wins(self):
        from routing_executor import _parallel_fallback

        mock_re = MagicMock()
        call_fn = MagicMock(return_value="parallel answer")
        result = _parallel_fallback(
            ["b1", "b2", "b3"], call_fn, [{"role": "user", "content": "hi"}],
            4096, None, mock_re,
        )
        assert result is not None
        backend, answer = result
        assert backend in ("b1", "b2", "b3")
        assert answer == "parallel answer"

    def test_all_fail_returns_none(self):
        from routing_executor import _parallel_fallback

        mock_re = MagicMock()
        call_fn = MagicMock(side_effect=Exception("fail"))
        result = _parallel_fallback(
            ["b1"], call_fn, [{"role": "user", "content": "hi"}],
            4096, None, mock_re,
        )
        assert result is None
