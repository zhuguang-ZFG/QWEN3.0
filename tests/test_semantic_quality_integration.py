"""Tests for semantic quality integration into the response pipeline."""

from unittest.mock import MagicMock, patch

import quality_history
import semantic_eval
from context_pipeline.response_pipeline import ResponseContext


def setup_function():
    quality_history.reset_all()


# -- semantic_quality_processor -----------------------------------------------

def test_semantic_quality_processor_records_score():
    from context_pipeline.response_processors import semantic_quality_processor

    ctx = ResponseContext(
        backend="test_backend",
        response_text="Here is how to implement a linked list in Python with Node class and append method.",
        status_code=200,
        latency_ms=500,
    )
    ctx.query = "How to implement a linked list in Python"

    result = semantic_quality_processor(ctx)

    trend = quality_history.get_quality_trend("test_backend")
    assert trend.sample_count == 1
    assert trend.average > 0


def test_semantic_quality_processor_skips_empty_response():
    from context_pipeline.response_processors import semantic_quality_processor

    ctx = ResponseContext(
        backend="test_backend",
        response_text="",
        status_code=200,
        latency_ms=500,
    )

    result = semantic_quality_processor(ctx)
    trend = quality_history.get_quality_trend("test_backend")
    assert trend.sample_count == 0


def test_semantic_quality_processor_skips_failed_quality():
    from context_pipeline.response_processors import semantic_quality_processor

    ctx = ResponseContext(
        backend="test_backend",
        response_text="Some text",
        status_code=200,
        latency_ms=500,
    )
    ctx.quality_ok = False  # Previous processor flagged issues

    result = semantic_quality_processor(ctx)
    trend = quality_history.get_quality_trend("test_backend")
    assert trend.sample_count == 0


def test_semantic_quality_processor_handles_import_error():
    """Processor should not crash if semantic_eval is unavailable."""
    from context_pipeline.response_processors import semantic_quality_processor

    ctx = ResponseContext(
        backend="test_backend",
        response_text="Some valid response text here.",
        status_code=200,
        latency_ms=500,
    )

    with patch.dict("sys.modules", {"semantic_eval": None}):
        # Should not raise even if semantic_eval import fails
        result = semantic_quality_processor(ctx)
        assert result is not None


# -- build_default_response_pipeline includes semantic_quality ---------------

def test_default_pipeline_includes_semantic_quality():
    from context_pipeline.response_processors import build_default_response_pipeline

    pipeline = build_default_response_pipeline()
    processor_names = [name for name, _ in pipeline._processors]
    assert "semantic_quality" in processor_names


def test_default_pipeline_order():
    """semantic_quality should come after quality_check but before memory_capture."""
    from context_pipeline.response_processors import build_default_response_pipeline

    pipeline = build_default_response_pipeline()
    names = [name for name, _ in pipeline._processors]
    assert names.index("quality_check") < names.index("semantic_quality")
    assert names.index("semantic_quality") < names.index("memory_capture")


# -- Full pipeline processing -------------------------------------------------

def test_full_pipeline_processes_semantic_quality():
    from context_pipeline.response_processors import build_default_response_pipeline

    pipeline = build_default_response_pipeline()
    ctx = ResponseContext(
        backend="pipeline_test",
        response_text="To sort a Python list, use sorted() or .sort() method. Both work well for most use cases.",
        status_code=200,
        latency_ms=300,
    )
    ctx.query = "How to sort a list in Python"

    result = pipeline.process(ctx)
    assert "semantic_quality" in result.processors_applied


# -- routing_executor integration ---------------------------------------------

def test_routing_executor_records_semantic_quality():
    """Verify routing_executor calls semantic_eval after successful response."""
    import sys

    import quality_history as qh
    import semantic_eval as se

    # Mock routing_engine so execute() can run
    mock_re = MagicMock()
    mock_re.health_tracker.is_cooled_down.return_value = False
    mock_re.health_tracker.record_success = MagicMock()
    mock_re.health_tracker.record_failure = MagicMock()
    mock_re.health_tracker.detect_and_reset_mass_failure = MagicMock()
    mock_re.budget_manager.record_usage = MagicMock()
    mock_re.budget_manager.is_budget_available.return_value = False

    mock_retry = MagicMock()
    mock_retry.is_retryable_error = MagicMock(return_value=False)

    call_fn = MagicMock(return_value="Here is how to implement sorting in Python using sorted().")

    messages = [{"role": "user", "content": "How to implement sorting"}]

    with patch.dict(sys.modules, {
        "routing_engine": mock_re,
        "opencode_retry_policy": mock_retry,
    }):
        from routing_executor import execute
        backend, answer, errors = execute(
            ["test_backend"], call_fn, messages=messages,
        )

    assert backend == "test_backend"
    assert answer == "Here is how to implement sorting in Python using sorted()."

    # Verify quality was recorded by the routing_executor hook
    trend = qh.get_quality_trend("test_backend")
    assert trend.sample_count == 1
    assert trend.average > 0
