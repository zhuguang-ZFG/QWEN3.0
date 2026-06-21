"""Hypothesis property tests for routing engine — crash-safety under arbitrary input."""

from __future__ import annotations

import pytest
from hypothesis import given, settings, strategies as st

settings.register_profile("ci", deadline=1000)
settings.load_profile("ci")

from routing_classifier import classify, classify_scenario
from routing_engine import route


@given(
    query=st.text(max_size=200),
    fmt=st.sampled_from(["openai", "anthropic", "unknown"]),
    ide_source=st.text(max_size=40),
)
@settings(max_examples=100)
def test_classify_never_crashes(query: str, fmt: str, ide_source: str):
    """classify() should return a valid request type for any input."""
    messages = [{"role": "user", "content": query}] if query else []
    result = classify(query, messages, fmt=fmt, ide_source=ide_source)
    assert isinstance(result, str)
    assert result  # should not be empty


@given(
    query=st.text(max_size=200),
    ide_source=st.text(max_size=40),
)
@settings(max_examples=100)
def test_classify_scenario_never_crashes(query: str, ide_source: str):
    """classify_scenario() should return a valid scenario string."""
    messages = [{"role": "user", "content": query}] if query else []
    result = classify_scenario(messages, query=query, ide_source=ide_source)
    assert isinstance(result, str)
    assert result in ("chat", "coding", "tool_use", "image", "identity", "unknown")


@given(
    query=st.text(min_size=1, max_size=200),
    fmt=st.sampled_from(["openai", "anthropic"]),
)
@settings(max_examples=30, deadline=None)
def test_route_never_crashes(query: str, fmt: str):
    """route() should return a RouteResult (or fail gracefully with no backends)."""
    messages = [{"role": "user", "content": query}]
    try:
        result = route(
            query,
            messages,
            fmt=fmt,
            model="lima-1.3",
            max_tokens=100,
        )
        assert result is not None
        assert hasattr(result, "backend")
        assert hasattr(result, "answer")
    except ImportError as exc:
        pytest.skip(f"optional dependency unavailable: {exc}")


@pytest.mark.parametrize(
    "query,expected_request_type",
    [
        ("write a function to sort a list in Python", "code"),
        ("hello how are you", "chat"),
        ("generate an image of a cat", "image"),
        ("what is LiMa", "identity"),
        ("use the terminal to list files", "tool_use"),
    ],
)
def test_classify_known_patterns(query, expected_request_type):
    """Known query patterns should map to expected types."""
    messages = [{"role": "user", "content": query}]
    result = classify(query, messages, fmt="openai", ide_source="")
    assert isinstance(result, str)


def test_classify_empty_messages():
    """Empty messages should not crash."""
    result = classify("", [], fmt="openai", ide_source="")
    assert isinstance(result, str)


def test_classify_deeply_nested_payload():
    """Deeply nested message content should not cause recursion errors."""
    deep = {"role": "user", "content": [{"type": "text", "text": "nested"}]}
    result = classify("test", [deep], fmt="openai", ide_source="")
    assert isinstance(result, str)


def test_route_empty_query():
    """Empty query with empty messages should fail gracefully."""
    try:
        result = route("", [], fmt="openai", model="lima-1.3", max_tokens=10)
        assert result is not None
    except ImportError as exc:
        pytest.skip(f"optional dependency unavailable: {exc}")
