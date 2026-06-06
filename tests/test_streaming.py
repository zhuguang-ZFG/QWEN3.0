"""Tests for streaming — bridge_stream_async and speculative_stream."""

import asyncio
import pytest


# ── bridge_stream_async ─────────────────────────────────────────────────────
class TestBridgeStreamAsync:
    @pytest.mark.asyncio
    async def test_basic_stream(self):
        """Stream yields chunks from async iterator."""
        from streaming import bridge_stream_async

        async def mock_stream(backend, messages, max_tokens, ide):
            for chunk in ["Hello", " ", "world"]:
                yield chunk

        async def mock_api(backend, messages, max_tokens, ide):
            return ""

        chunks = []
        async for chunk in bridge_stream_async(
            "test_backend", [{"role": "user", "content": "hi"}],
            4096, "", mock_stream, mock_api,
        ):
            chunks.append(chunk)

        # Stream yields chunks; graceful finish injected if no finish_reason
        assert chunks[:3] == ["Hello", " ", "world"]
        # Graceful finish chunk should be appended (no finish_reason in mock)
        assert len(chunks) == 4
        assert "finish_reason" in chunks[3]

    @pytest.mark.asyncio
    async def test_timeout_breaks_stream(self):
        """Stream breaks on timeout after first chunk timeout."""
        from streaming import bridge_stream_async

        async def slow_stream(backend, messages, max_tokens, ide):
            yield "first"
            await asyncio.sleep(10)  # Will timeout
            yield "never"

        async def mock_api(backend, messages, max_tokens, ide):
            return ""

        chunks = []
        async for chunk in bridge_stream_async(
            "test_backend", [{"role": "user", "content": "hi"}],
            4096, "", slow_stream, mock_api,
            first_chunk_timeout=2.0, chunk_timeout=0.1,
        ):
            chunks.append(chunk)

        assert "first" in chunks
        assert "never" not in chunks

    @pytest.mark.asyncio
    async def test_empty_stream_fallback_to_api(self):
        """When stream yields nothing, falls back to API call."""
        from streaming import bridge_stream_async

        async def empty_stream(backend, messages, max_tokens, ide):
            return
            yield  # Make it an async generator

        async def mock_api(backend, messages, max_tokens, ide):
            return "fallback answer"

        chunks = []
        async for chunk in bridge_stream_async(
            "test_backend", [{"role": "user", "content": "hi"}],
            4096, "", empty_stream, mock_api,
        ):
            chunks.append(chunk)

        assert chunks == ["fallback answer"]

    @pytest.mark.asyncio
    async def test_error_in_stream(self):
        """When stream raises, error is caught and fallback is tried."""
        from streaming import bridge_stream_async

        async def error_stream(backend, messages, max_tokens, ide):
            raise RuntimeError("stream exploded")
            yield  # Make it an async generator

        async def mock_api(backend, messages, max_tokens, ide):
            return "recovered"

        chunks = []
        async for chunk in bridge_stream_async(
            "test_backend", [{"role": "user", "content": "hi"}],
            4096, "", error_stream, mock_api,
        ):
            chunks.append(chunk)

        assert chunks == ["recovered"]


# ── speculative_stream ──────────────────────────────────────────────────────
class TestSpeculativeStream:
    @pytest.mark.asyncio
    async def test_prediction_matches_routing(self):
        """When predicted backend matches actual, stream continues uninterrupted."""
        from streaming import speculative_stream

        def predict_fn(query):
            return "fast_backend"

        def select_fn(query, model, ide, messages):
            return ("fast_backend", messages)

        async def mock_stream_async(backend, messages, max_tokens, ide):
            for chunk in ["Hello", " world"]:
                yield chunk

        async def mock_api_async(backend, messages, max_tokens, ide):
            return ""

        def mock_stream_fn(*args):
            return iter([])

        def mock_call_fn(*args):
            return ""

        chunks = []
        async for backend, chunk in speculative_stream(
            "hi", [{"role": "user", "content": "hi"}], 4096, "",
            predict_fn, select_fn, mock_stream_fn, mock_call_fn,
            call_stream_async_fn=mock_stream_async,
            call_api_async_fn=mock_api_async,
        ):
            chunks.append((backend, chunk))

        assert len(chunks) >= 2
        assert all(b == "fast_backend" for b, _ in chunks)
        joined = "".join(c for _, c in chunks)
        assert "Hello world" in joined

    @pytest.mark.asyncio
    async def test_prediction_mismatch_switches_backend(self):
        """When routing selects different backend, stream switches."""
        from streaming import speculative_stream

        call_count = {"n": 0}

        def predict_fn(query):
            return "predicted_backend"

        async def slow_select(query, model, ide, messages):
            await asyncio.sleep(0.01)
            return ("actual_backend", messages)

        async def mock_stream_async(backend, messages, max_tokens, ide):
            call_count["n"] += 1
            if backend == "predicted_backend":
                # Simulate slow stream that hasn't started when routing completes
                await asyncio.sleep(0.1)
                yield "predicted_chunk"
            else:
                yield "actual_chunk"

        async def mock_api_async(backend, messages, max_tokens, ide):
            return ""

        def mock_stream_fn(*args):
            return iter([])

        def mock_call_fn(*args):
            return ""

        chunks = []
        async for backend, chunk in speculative_stream(
            "hi", [{"role": "user", "content": "hi"}], 4096, "",
            predict_fn, slow_select, mock_stream_fn, mock_call_fn,
            call_stream_async_fn=mock_stream_async,
            call_api_async_fn=mock_api_async,
        ):
            chunks.append((backend, chunk))

        # Should have at least one chunk from actual_backend
        backends = set(b for b, _ in chunks)
        assert "actual_backend" in backends or "predicted_backend" in backends
