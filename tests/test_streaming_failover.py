"""Tests for mid-stream failover in bridge_stream_async."""

import asyncio
import json
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

from streaming import bridge_stream_async, _track_text_from_chunk
from streaming_state import StreamState


def _make_sse_chunk(text: str, finish_reason: str | None = None) -> str:
    """Build an OpenAI-format SSE chunk string."""
    delta = {"content": text} if text else {}
    chunk = {
        "id": "chatcmpl-test",
        "object": "chat.completion.chunk",
        "created": 1700000000,
        "model": "test-model",
        "choices": [{
            "index": 0,
            "delta": delta,
            "finish_reason": finish_reason,
        }],
    }
    return f"data: {json.dumps(chunk)}\n"


async def _collect_chunks(stream: AsyncIterator[str]) -> list[str]:
    """Collect all chunks from an async iterator."""
    chunks = []
    async for chunk in stream:
        chunks.append(chunk)
    return chunks


class TestBridgeStreamFailover:
    @pytest.mark.asyncio
    async def test_normal_stream_no_failover(self):
        """Stream completes normally -- no failover needed."""
        chunks = [
            _make_sse_chunk("Hello "),
            _make_sse_chunk("world"),
            _make_sse_chunk("", finish_reason="stop"),
        ]

        async def mock_stream_async(backend, messages, max_tokens, ide):
            for c in chunks:
                yield c

        async def mock_api_async(backend, messages, max_tokens, ide):
            return ""

        result = await _collect_chunks(
            bridge_stream_async(
                "backend_a", [{"role": "user", "content": "Hi"}],
                100, "test",
                call_stream_async_fn=mock_stream_async,
                call_api_async_fn=mock_api_async,
                fallback_backends=["backend_b"],
            )
        )

        assert len(result) == 3
        assert "Hello " in result[0]
        assert "world" in result[1]

    @pytest.mark.asyncio
    async def test_failover_on_timeout(self):
        """Primary backend times out mid-stream, failover to backup succeeds."""
        primary_chunks = [
            _make_sse_chunk("Part one "),
            _make_sse_chunk("of the "),
            # Then it hangs (we simulate by raising TimeoutError via slow iterator)
        ]
        backup_chunks = [
            _make_sse_chunk("response "),
            _make_sse_chunk("continued."),
            _make_sse_chunk("", finish_reason="stop"),
        ]

        call_count = {"n": 0}

        async def mock_stream_async(backend, messages, max_tokens, ide):
            call_count["n"] += 1
            if backend == "backend_a":
                for c in primary_chunks:
                    yield c
                # Simulate timeout: sleep longer than timeout
                await asyncio.sleep(100)
            else:
                for c in backup_chunks:
                    yield c

        async def mock_api_async(backend, messages, max_tokens, ide):
            return ""

        result = await _collect_chunks(
            bridge_stream_async(
                "backend_a", [{"role": "user", "content": "Hi"}],
                100, "test",
                call_stream_async_fn=mock_stream_async,
                call_api_async_fn=mock_api_async,
                first_chunk_timeout=0.1,
                chunk_timeout=0.1,
                fallback_backends=["backend_b"],
            )
        )

        # Should have chunks from both backends
        all_text = "".join(result)
        assert "Part one " in all_text
        assert "of the " in all_text
        # Backup should have contributed
        assert call_count["n"] >= 2  # Called both backends

    @pytest.mark.asyncio
    async def test_failover_on_exception(self):
        """Primary backend raises exception mid-stream."""
        backup_chunks = [
            _make_sse_chunk("Recovery "),
            _make_sse_chunk("text."),
            _make_sse_chunk("", finish_reason="stop"),
        ]

        async def mock_stream_async(backend, messages, max_tokens, ide):
            if backend == "backend_a":
                yield _make_sse_chunk("Start ")
                raise ConnectionError("Connection reset")
            else:
                for c in backup_chunks:
                    yield c

        async def mock_api_async(backend, messages, max_tokens, ide):
            return ""

        result = await _collect_chunks(
            bridge_stream_async(
                "backend_a", [{"role": "user", "content": "Hi"}],
                100, "test",
                call_stream_async_fn=mock_stream_async,
                call_api_async_fn=mock_api_async,
                fallback_backends=["backend_b"],
            )
        )

        all_text = "".join(result)
        assert "Start " in all_text
        assert "Recovery " in all_text

    @pytest.mark.asyncio
    async def test_no_failover_without_fallback_backends(self):
        """Without fallback_backends, failure just triggers graceful finish."""
        async def mock_stream_async(backend, messages, max_tokens, ide):
            yield _make_sse_chunk("Partial ")
            raise ConnectionError("fail")

        async def mock_api_async(backend, messages, max_tokens, ide):
            return ""

        result = await _collect_chunks(
            bridge_stream_async(
                "backend_a", [{"role": "user", "content": "Hi"}],
                100, "test",
                call_stream_async_fn=mock_stream_async,
                call_api_async_fn=mock_api_async,
                # No fallback_backends
            )
        )

        all_text = "".join(result)
        assert "Partial " in all_text

    @pytest.mark.asyncio
    async def test_on_failover_callback(self):
        """The on_failover callback is invoked during failover."""
        callback = MagicMock()

        async def mock_stream_async(backend, messages, max_tokens, ide):
            if backend == "backend_a":
                yield _make_sse_chunk("A text ")
                raise ConnectionError("fail")
            else:
                yield _make_sse_chunk("B text")
                yield _make_sse_chunk("", finish_reason="stop")

        async def mock_api_async(backend, messages, max_tokens, ide):
            return ""

        await _collect_chunks(
            bridge_stream_async(
                "backend_a", [{"role": "user", "content": "Hi"}],
                100, "test",
                call_stream_async_fn=mock_stream_async,
                call_api_async_fn=mock_api_async,
                fallback_backends=["backend_b"],
                on_failover=callback,
            )
        )

        callback.assert_called_once()
        args = callback.call_args
        assert args[0][0] == "backend_a"  # failed backend
        assert args[0][1] == "backend_b"  # new backend
        assert isinstance(args[0][2], StreamState)

    @pytest.mark.asyncio
    async def test_max_failovers_respected(self):
        """Failover stops after max_failovers attempts."""
        call_order = []

        async def mock_stream_async(backend, messages, max_tokens, ide):
            call_order.append(backend)
            yield _make_sse_chunk(f"text from {backend} ")
            raise ConnectionError(f"{backend} failed")

        async def mock_api_async(backend, messages, max_tokens, ide):
            return ""

        await _collect_chunks(
            bridge_stream_async(
                "backend_a", [{"role": "user", "content": "Hi"}],
                100, "test",
                call_stream_async_fn=mock_stream_async,
                call_api_async_fn=mock_api_async,
                fallback_backends=["backend_b", "backend_c", "backend_d"],
                max_failovers=2,
            )
        )

        # Should try at most primary + 2 failovers = 3 backends total
        assert len(call_order) <= 3


class TestTrackTextFromChunk:
    def test_track_sse_text_chunk(self):
        state = StreamState()
        chunk = _make_sse_chunk("Hello ")
        _track_text_from_chunk(state, chunk)
        assert state.accumulated_text == "Hello "

    def test_track_meta_chunk(self):
        state = StreamState()
        _track_text_from_chunk(state, '__LIMA_META__:{"usage": {"prompt_tokens": 10}}')
        assert state.usage == {"prompt_tokens": 10}
        assert state.accumulated_text == ""

    def test_track_done_chunk(self):
        state = StreamState()
        _track_text_from_chunk(state, "data: [DONE]\n")
        assert state.accumulated_text == ""

    def test_track_empty_chunk(self):
        state = StreamState()
        _track_text_from_chunk(state, "")
        assert state.accumulated_text == ""

    def test_track_finish_chunk_no_text(self):
        state = StreamState()
        chunk = _make_sse_chunk("", finish_reason="stop")
        _track_text_from_chunk(state, chunk)
        assert state.accumulated_text == ""

    def test_track_raw_text_fallback(self):
        state = StreamState()
        _track_text_from_chunk(state, "raw text not in SSE format")
        assert state.accumulated_text == "raw text not in SSE format"
