"""Tests for streaming_retry continuation prompt construction."""

import pytest

from streaming_retry import (
    build_continuation_messages,
    extract_partial_from_state,
    should_attempt_failover,
)


class TestBuildContinuationMessages:
    def test_empty_partial_returns_original(self):
        original = [
            {"role": "user", "content": "Hello"},
        ]
        result = build_continuation_messages(original, "")
        assert result == original

    def test_whitespace_only_partial_returns_original(self):
        original = [{"role": "user", "content": "Hello"}]
        result = build_continuation_messages(original, "   \n  ")
        assert result == original

    def test_basic_continuation(self):
        original = [
            {"role": "user", "content": "Write a story about a cat."},
        ]
        partial = "Once upon a time, there was a cat named"
        result = build_continuation_messages(original, partial)

        assert len(result) == 3  # original(1) + assistant partial + user instruction
        assert result[0] == {"role": "user", "content": "Write a story about a cat."}
        assert result[1] == {"role": "assistant", "content": partial}
        assert result[2]["role"] == "user"
        assert "continue" in result[2]["content"].lower()

    def test_preserves_system_messages(self):
        original = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"},
        ]
        partial = "Hi there! How can"
        result = build_continuation_messages(original, partial)

        assert result[0]["role"] == "system"
        assert result[0]["content"] == "You are a helpful assistant."
        assert result[1] == {"role": "user", "content": "Hello"}
        assert result[2]["role"] == "assistant"
        assert result[3]["role"] == "user"

    def test_truncates_long_partial(self):
        original = [{"role": "user", "content": "Explain physics."}]
        partial = "A" * 10000  # Very long partial
        result = build_continuation_messages(original, partial, max_partial_chars=500)

        assistant_msg = result[1]
        assert assistant_msg["role"] == "assistant"
        assert len(assistant_msg["content"]) == 500
        # Should keep the tail
        assert assistant_msg["content"] == "A" * 500

    def test_does_not_mutate_original(self):
        original = [{"role": "user", "content": "Hello"}]
        original_copy = list(original)
        build_continuation_messages(original, "partial text")
        assert original == original_copy


class TestExtractPartialFromState:
    def test_basic_extraction(self):
        assert extract_partial_from_state("Hello world") == "Hello world"

    def test_strips_meta_lines(self):
        text = "Hello\n__LIMA_META__:{\"usage\": {}}\nworld"
        result = extract_partial_from_state(text)
        assert "__LIMA_META__" not in result
        assert "Hello" in result
        assert "world" in result

    def test_strips_trailing_whitespace(self):
        result = extract_partial_from_state("Hello world   \n  ")
        assert result == "Hello world"

    def test_preserves_trailing_whitespace_when_requested(self):
        result = extract_partial_from_state(
            "Hello world   ", strip_trailing_whitespace=False
        )
        assert result == "Hello world   "


class TestShouldAttemptFailover:
    def test_first_failover_allowed(self):
        assert should_attempt_failover("some text", chunk_count=5, failover_count=0) is True

    def test_max_failovers_reached(self):
        assert should_attempt_failover("some text", chunk_count=5, failover_count=2) is False

    def test_max_failovers_custom(self):
        assert should_attempt_failover(
            "text", chunk_count=5, failover_count=3, max_failovers=5
        ) is True

    def test_too_few_chunks(self):
        assert should_attempt_failover(
            "", chunk_count=0, failover_count=0, min_chunks_for_failover=1
        ) is False

    def test_enough_chunks(self):
        assert should_attempt_failover(
            "text", chunk_count=10, failover_count=0, min_chunks_for_failover=5
        ) is True
