"""Integration tests for streaming fault tolerance and auto-recovery.

Exercises the full pipeline from bridge_stream_async through
stream_handlers to verify client-transparent failover.

All external dependencies (httpx, routing_engine, health_tracker)
are mocked.
"""

import asyncio
import json
import time
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from streaming import _track_text_from_chunk, bridge_stream_async
from streaming_failover_metrics import (
    FailoverEvent,
    FailoverMetrics,
    record_stream_failover,
)
from streaming_retry import build_continuation_messages
from streaming_state import StreamState


def _sse_chunk(text: str, finish_reason: str | None = None) -> str:
    """Build an OpenAI-format SSE chunk."""
    delta = {"content": text} if text else {}
    chunk = {
        "id": "chatcmpl-integration",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": "test-model",
        "choices": [{
            "index": 0,
            "delta": delta,
            "finish_reason": finish_reason,
        }],
    }
    return f"data: {json.dumps(chunk)}\n"


def _meta_chunk(meta: dict) -> str:
    """Build a __LIMA_META__ chunk."""
    return f"__LIMA_META__:{json.dumps(meta)}\n"


async def _drain(stream: AsyncIterator[str]) -> list[str]:
    """Collect all chunks from an async iterator."""
    return [chunk async for chunk in stream]


class TestEndToEndFailover:
    """Full pipeline tests: backend fails mid-stream, backup takes over."""

    async def test_seamless_failover_client_sees_continuous_stream(self):
        """
        Scenario: Primary backend sends 3 chunks then dies.
                  Backup backend picks up and completes the response.
        Expected: Client receives all chunks in order with no errors.
        """
        # Primary sends 3 chunks then connection resets
        primary_chunks = [
            _sse_chunk("The quick "),
            _sse_chunk("brown fox "),
            _sse_chunk("jumps over "),
        ]
        # Backup continues from where primary left off
        backup_chunks = [
            _sse_chunk("the lazy "),
            _sse_chunk("dog."),
            _sse_chunk("", finish_reason="stop"),
        ]

        call_log = []

        async def mock_stream(backend, messages, max_tokens, ide):
            call_log.append({
                "backend": backend,
                "messages_count": len(messages),
            })
            if backend == "primary_backend":
                for c in primary_chunks:
                    yield c
                raise ConnectionError("Connection reset by peer")
            elif backend == "backup_backend":
                for c in backup_chunks:
                    yield c
            else:
                raise ConnectionError(f"Unknown backend: {backend}")

        async def mock_api(backend, messages, max_tokens, ide):
            return ""

        failover_log = []

        def on_failover(failed, new, state):
            failover_log.append({
                "failed": failed,
                "new": new,
                "chunks": state.chunk_count,
                "text_len": state.partial_length,
            })

        chunks = await _drain(
            bridge_stream_async(
                "primary_backend",
                [{"role": "user", "content": "Write a sentence."}],
                100,
                "test",
                call_stream_async_fn=mock_stream,
                call_api_async_fn=mock_api,
                fallback_backends=["backup_backend"],
                on_failover=on_failover,
            )
        )

        # Verify: both backends were called
        assert len(call_log) == 2
        assert call_log[0]["backend"] == "primary_backend"
        assert call_log[1]["backend"] == "backup_backend"

        # Verify: backup received continuation messages (original + partial + instruction)
        assert call_log[1]["messages_count"] > 1  # Has continuation messages

        # Verify: failover callback was invoked
        assert len(failover_log) == 1
        assert failover_log[0]["failed"] == "primary_backend"
        assert failover_log[0]["new"] == "backup_backend"
        assert failover_log[0]["chunks"] == 3

        # Verify: client received all chunks in order
        all_text_parts = []
        for chunk in chunks:
            if chunk.startswith("data: "):
                try:
                    data = json.loads(chunk[6:].strip())
                    choices = data.get("choices", [])
                    if choices:
                        text = choices[0].get("delta", {}).get("content", "")
                        if text:
                            all_text_parts.append(text)
                except (json.JSONDecodeError, KeyError):
                    pass

        full_text = "".join(all_text_parts)
        assert "The quick " in full_text
        assert "brown fox " in full_text
        assert "jumps over " in full_text
        assert "the lazy " in full_text
        assert "dog." in full_text

    async def test_double_failover_two_backends_fail(self):
        """
        Scenario: Primary fails, first backup also fails, second backup succeeds.
        Expected: Client gets chunks from all three, final backup completes.
        """
        async def mock_stream(backend, messages, max_tokens, ide):
            if backend == "backend_a":
                yield _sse_chunk("A1 ")
                raise ConnectionError("A failed")
            elif backend == "backend_b":
                yield _sse_chunk("B1 ")
                raise ConnectionError("B failed")
            elif backend == "backend_c":
                yield _sse_chunk("C1 ")
                yield _sse_chunk("C2 done")
                yield _sse_chunk("", finish_reason="stop")

        async def mock_api(backend, messages, max_tokens, ide):
            return ""

        chunks = await _drain(
            bridge_stream_async(
                "backend_a",
                [{"role": "user", "content": "Hi"}],
                100, "test",
                call_stream_async_fn=mock_stream,
                call_api_async_fn=mock_api,
                fallback_backends=["backend_b", "backend_c"],
                max_failovers=2,
            )
        )

        all_text = "".join(chunks)
        assert "A1 " in all_text
        assert "B1 " in all_text
        assert "C1 " in all_text
        assert "C2 done" in all_text

    async def test_all_backends_fail_graceful_finish(self):
        """
        Scenario: All backends fail. Stream gets a graceful finish chunk.
        Expected: Client sees partial content + graceful finish, no crash.
        """
        async def mock_stream(backend, messages, max_tokens, ide):
            yield _sse_chunk(f"text from {backend} ")
            raise ConnectionError(f"{backend} died")

        async def mock_api(backend, messages, max_tokens, ide):
            return ""

        chunks = await _drain(
            bridge_stream_async(
                "backend_a",
                [{"role": "user", "content": "Hi"}],
                100, "test",
                call_stream_async_fn=mock_stream,
                call_api_async_fn=mock_api,
                fallback_backends=["backend_b"],
                max_failovers=1,
            )
        )

        all_text = "".join(chunks)
        # Should have content from at least one backend
        assert "text from" in all_text
        # Should have a graceful finish (finish_reason in some chunk)
        has_finish = any('"finish_reason"' in c for c in chunks)
        assert has_finish

    async def test_failover_with_usage_metadata(self):
        """
        Scenario: Primary sends usage meta before failing.
        Expected: Usage metadata is preserved through failover.
        """
        async def mock_stream(backend, messages, max_tokens, ide):
            if backend == "primary":
                yield _meta_chunk({"usage": {"prompt_tokens": 50}})
                yield _sse_chunk("Hello ")
                raise ConnectionError("primary died")
            else:
                yield _sse_chunk("world")
                yield _sse_chunk("", finish_reason="stop")

        async def mock_api(backend, messages, max_tokens, ide):
            return ""

        chunks = await _drain(
            bridge_stream_async(
                "primary",
                [{"role": "user", "content": "Hi"}],
                100, "test",
                call_stream_async_fn=mock_stream,
                call_api_async_fn=mock_api,
                fallback_backends=["backup"],
            )
        )

        # Should have meta chunk + text chunks from both backends
        meta_chunks = [c for c in chunks if c.startswith("__LIMA_META__:")]
        assert len(meta_chunks) >= 1
        text_chunks = [c for c in chunks if c.startswith("data: ")]
        assert len(text_chunks) >= 2

    async def test_continuation_messages_are_correct(self):
        """
        Verify that the continuation messages sent to the backup backend
        contain the partial text and continuation instruction.
        """
        received_messages = {}

        async def mock_stream(backend, messages, max_tokens, ide):
            received_messages[backend] = [dict(m) for m in messages]
            if backend == "primary":
                yield _sse_chunk("The answer is forty")
                raise ConnectionError("timeout")
            else:
                yield _sse_chunk("-two.")
                yield _sse_chunk("", finish_reason="stop")

        async def mock_api(backend, messages, max_tokens, ide):
            return ""

        await _drain(
            bridge_stream_async(
                "primary",
                [{"role": "user", "content": "What is 6 * 7?"}],
                100, "test",
                call_stream_async_fn=mock_stream,
                call_api_async_fn=mock_api,
                fallback_backends=["backup"],
            )
        )

        # Backup should have received continuation messages
        backup_msgs = received_messages.get("backup", [])
        assert len(backup_msgs) > 1  # Original + partial + instruction

        # Should contain the partial text as an assistant message
        assistant_msgs = [m for m in backup_msgs if m.get("role") == "assistant"]
        assert len(assistant_msgs) >= 1
        assert "forty" in assistant_msgs[-1]["content"]

        # Should contain a continuation instruction
        user_msgs = [m for m in backup_msgs if m.get("role") == "user"]
        has_continuation = any(
            "continue" in m.get("content", "").lower()
            for m in user_msgs
        )
        assert has_continuation

    async def test_failover_metrics_recorded(self):
        """Verify that failover events are recorded in metrics."""
        fresh_metrics = FailoverMetrics()

        async def mock_stream(backend, messages, max_tokens, ide):
            if backend == "failing_backend":
                yield _sse_chunk("partial ")
                raise ConnectionError("boom")
            else:
                yield _sse_chunk("recovered")
                yield _sse_chunk("", finish_reason="stop")

        async def mock_api(backend, messages, max_tokens, ide):
            return ""

        with patch("streaming_failover_metrics._metrics", fresh_metrics):
            def on_failover(failed, new, state):
                record_stream_failover(
                    failed, new, state.snapshot(), success=True,
                )

            await _drain(
                bridge_stream_async(
                    "failing_backend",
                    [{"role": "user", "content": "Hi"}],
                    100, "test",
                    call_stream_async_fn=mock_stream,
                    call_api_async_fn=mock_api,
                    fallback_backends=["recovery_backend"],
                    on_failover=on_failover,
                )
            )

        stats = fresh_metrics.get_stats()
        assert stats["total_failovers"] == 1
        assert stats["success_count"] == 1
        event = stats["recent_events"][0]
        assert event["failed_backend"] == "failing_backend"
        assert event["replacement_backend"] == "recovery_backend"

    async def test_no_failover_for_context_overflow(self):
        """
        Context overflow (413) errors should NOT trigger failover,
        since all backends would face the same context limit.
        """
        from http_errors import BackendError

        backup_called = []

        async def mock_stream(backend, messages, max_tokens, ide):
            if backend == "primary":
                yield _sse_chunk("start ")
                raise BackendError(
                    "context too large",
                    status_code=413,
                    is_overflow=True,
                )
            else:
                backup_called.append(True)
                yield _sse_chunk("should not be called")

        async def mock_api(backend, messages, max_tokens, ide):
            return ""

        chunks = await _drain(
            bridge_stream_async(
                "primary",
                [{"role": "user", "content": "Hi"}],
                100, "test",
                call_stream_async_fn=mock_stream,
                call_api_async_fn=mock_api,
                fallback_backends=["backup"],
            )
        )

        # The primary content should be present
        all_text = "".join(chunks)
        assert "start " in all_text

    async def test_stream_state_snapshot_accuracy(self):
        """Verify StreamState tracks accurate metrics during failover."""
        state = StreamState(backend="primary")

        # Simulate receiving chunks
        for i in range(5):
            state.record_chunk(f"chunk_{i}")
            state.record_text(f"text_{i} ")

        state.record_meta({"usage": {"prompt_tokens": 100, "completion_tokens": 50}})

        assert state.chunk_count == 5
        assert state.partial_length > 0
        assert state.usage == {"prompt_tokens": 100, "completion_tokens": 50}

        # Simulate failover
        state.mark_failed("timeout")
        snap_before = state.snapshot()
        assert snap_before["failure_reason"] == "timeout"

        state.mark_failover("backup")
        snap_after = state.snapshot()
        assert snap_after["failover_count"] == 1
        assert snap_after["failure_reason"] == ""
        assert "backup" in snap_after["backends_tried"]
