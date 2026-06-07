"""Tests for streaming_state.StreamState."""

import time

import pytest

from streaming_state import StreamState


class TestStreamState:
    def test_initial_state(self):
        state = StreamState(backend="backend_a")
        assert state.backend == "backend_a"
        assert state.accumulated_text == ""
        assert state.chunk_count == 0
        assert state.received_finish is False
        assert state.failover_count == 0
        assert state.backends_tried == []
        assert state.has_content is False
        assert state.is_complete is False
        assert state.partial_length == 0

    def test_record_chunk(self):
        state = StreamState()
        state.record_chunk("chunk1")
        state.record_chunk("chunk2")
        assert state.chunk_count == 2
        assert state.raw_chunks == ["chunk1", "chunk2"]

    def test_record_text(self):
        state = StreamState()
        state.record_text("Hello ")
        state.record_text("world")
        assert state.accumulated_text == "Hello world"
        assert state.has_content is True
        assert state.partial_length == 11

    def test_record_meta_usage(self):
        state = StreamState()
        state.record_meta({"usage": {"prompt_tokens": 10, "completion_tokens": 5}})
        assert state.usage == {"prompt_tokens": 10, "completion_tokens": 5}

    def test_record_meta_merges(self):
        state = StreamState()
        state.record_meta({"usage": {"prompt_tokens": 10}})
        state.record_meta({"usage": {"completion_tokens": 20}})
        assert state.usage == {"prompt_tokens": 10, "completion_tokens": 20}

    def test_mark_failed(self):
        state = StreamState(backend="backend_a")
        state.mark_failed("timeout after 30s")
        assert state.failure_reason == "timeout after 30s"
        assert state.failed_at is not None

    def test_mark_failover(self):
        state = StreamState(backend="backend_a")
        state.mark_failed("timeout")
        state.mark_failover("backend_b")
        assert state.backend == "backend_b"
        assert state.failover_count == 1
        assert state.backends_tried == ["backend_b"]
        assert state.failure_reason == ""
        assert state.failed_at is None

    def test_multiple_failovers(self):
        state = StreamState(backend="backend_a")
        state.mark_failover("backend_b")
        state.mark_failover("backend_c")
        assert state.failover_count == 2
        assert state.backends_tried == ["backend_b", "backend_c"]
        assert state.backend == "backend_c"

    def test_elapsed_sec(self):
        state = StreamState(started_at=time.time() - 5.0)
        assert state.elapsed_sec >= 4.9

    def test_snapshot(self):
        state = StreamState(backend="backend_a", started_at=time.time() - 2.0)
        state.record_text("Hello")
        state.record_chunk("chunk1")
        state.mark_failover("backend_b")
        snap = state.snapshot()
        assert snap["backend"] == "backend_b"
        assert snap["chunk_count"] == 1
        assert snap["text_length"] == 5
        assert snap["failover_count"] == 1
        assert snap["backends_tried"] == ["backend_b"]
        assert snap["elapsed_sec"] >= 1.9
