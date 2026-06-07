"""Tests for stream handler failover wiring."""

import json
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_sse_chunk(text: str, finish_reason: str | None = None) -> str:
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


async def _collect(gen: AsyncIterator[str]) -> list[str]:
    result = []
    async for item in gen:
        result.append(item)
    return result


class TestRealStreamChunksAsyncFailover:
    @pytest.mark.asyncio
    async def test_passes_fallback_backends(self):
        """real_stream_chunks_async passes fallback_backends to bridge_stream_async."""
        from routes import stream_handlers

        captured_kwargs = {}

        async def mock_bridge(*args, **kwargs):
            captured_kwargs.update(kwargs)
            yield _make_sse_chunk("text")
            yield _make_sse_chunk("", finish_reason="stop")

        with patch.object(
            stream_handlers.streaming_mod, "bridge_stream_async", mock_bridge
        ):
            await _collect(
                stream_handlers.real_stream_chunks_async(
                    "backend_a", [{"role": "user", "content": "Hi"}],
                    fallback_backends=["backend_b", "backend_c"],
                    max_failovers=2,
                )
            )

        assert captured_kwargs.get("fallback_backends") == ["backend_b", "backend_c"]
        assert captured_kwargs.get("max_failovers") == 2

    @pytest.mark.asyncio
    async def test_passes_on_failover_callback(self):
        """on_failover callback is forwarded correctly."""
        from routes import stream_handlers

        captured_kwargs = {}
        callback = MagicMock()

        async def mock_bridge(*args, **kwargs):
            captured_kwargs.update(kwargs)
            yield _make_sse_chunk("text")

        with patch.object(
            stream_handlers.streaming_mod, "bridge_stream_async", mock_bridge
        ):
            await _collect(
                stream_handlers.real_stream_chunks_async(
                    "backend_a", [],
                    on_failover=callback,
                )
            )

        assert captured_kwargs.get("on_failover") is callback

    @pytest.mark.asyncio
    async def test_defaults_are_backward_compatible(self):
        """Calling without failover params still works (backward compatibility)."""
        from routes import stream_handlers

        captured_kwargs = {}

        async def mock_bridge(*args, **kwargs):
            captured_kwargs.update(kwargs)
            yield _make_sse_chunk("text")

        with patch.object(
            stream_handlers.streaming_mod, "bridge_stream_async", mock_bridge
        ):
            await _collect(
                stream_handlers.real_stream_chunks_async(
                    "backend_a", [{"role": "user", "content": "Hi"}],
                )
            )

        # Defaults should be passed through: fallback_backends=None, max_failovers=2
        assert captured_kwargs.get("fallback_backends") is None
        assert captured_kwargs.get("max_failovers") == 2
        assert captured_kwargs.get("on_failover") is None


class TestSpeculativeStreamChunksFailover:
    @pytest.mark.asyncio
    async def test_passes_fallback_backends(self):
        """speculative_stream_chunks passes fallback_backends to speculative_stream."""
        from routes import stream_handlers

        captured_kwargs = {}

        async def mock_speculative(*args, **kwargs):
            captured_kwargs.update(kwargs)
            yield ("backend_a", _make_sse_chunk("text"))

        with patch.object(
            stream_handlers.streaming_mod, "speculative_stream", mock_speculative
        ):
            await _collect(
                stream_handlers.speculative_stream_chunks(
                    "query", [],
                    fallback_backends=["backend_x"],
                    max_failovers=1,
                )
            )

        assert captured_kwargs.get("fallback_backends") == ["backend_x"]
        assert captured_kwargs.get("max_failovers") == 1

    @pytest.mark.asyncio
    async def test_defaults_are_backward_compatible(self):
        """Calling without failover params still works (backward compatibility)."""
        from routes import stream_handlers

        captured_kwargs = {}

        async def mock_speculative(*args, **kwargs):
            captured_kwargs.update(kwargs)
            yield ("backend_a", _make_sse_chunk("text"))

        with patch.object(
            stream_handlers.streaming_mod, "speculative_stream", mock_speculative
        ):
            await _collect(
                stream_handlers.speculative_stream_chunks(
                    "query", [],
                )
            )

        assert captured_kwargs.get("fallback_backends") is None
        assert captured_kwargs.get("max_failovers") == 2


class TestGetFallbackBackends:
    def test_returns_empty_on_import_error(self):
        """_get_fallback_backends handles missing modules gracefully."""
        from routes.chat_stream import _get_fallback_backends

        with patch.dict("sys.modules", {"routing_engine": None}):
            result = _get_fallback_backends("primary", [])
            assert isinstance(result, list)

    def test_excludes_primary_backend(self):
        """Primary backend is excluded from fallback list."""
        from routes.chat_stream import _get_fallback_backends

        mock_routing = MagicMock()
        mock_routing.select.return_value = ["primary", "backup_a", "backup_b"]
        mock_health = MagicMock()
        mock_health.get_health_map.return_value = {}

        with patch.dict("sys.modules", {
            "routing_engine": mock_routing,
            "health_tracker": mock_health,
        }):
            result = _get_fallback_backends("primary", [])

        assert "primary" not in result
        assert "backup_a" in result
        assert "backup_b" in result

    def test_limits_to_three_fallbacks(self):
        """At most 3 fallback backends are returned."""
        from routes.chat_stream import _get_fallback_backends

        mock_routing = MagicMock()
        mock_routing.select.return_value = [
            "primary", "b1", "b2", "b3", "b4", "b5"
        ]
        mock_health = MagicMock()
        mock_health.get_health_map.return_value = {}

        with patch.dict("sys.modules", {
            "routing_engine": mock_routing,
            "health_tracker": mock_health,
        }):
            result = _get_fallback_backends("primary", [])

        assert len(result) <= 3

    def test_returns_empty_when_no_other_backends(self):
        """Returns empty list when only primary is available."""
        from routes.chat_stream import _get_fallback_backends

        mock_routing = MagicMock()
        mock_routing.select.return_value = ["primary"]
        mock_health = MagicMock()
        mock_health.get_health_map.return_value = {}

        with patch.dict("sys.modules", {
            "routing_engine": mock_routing,
            "health_tracker": mock_health,
        }):
            result = _get_fallback_backends("primary", [])

        assert result == []

    def test_uses_ide_req_type_when_ide_source_given(self):
        """When ide_source is provided, req_type should be 'ide'."""
        from routes.chat_stream import _get_fallback_backends

        mock_routing = MagicMock()
        mock_routing.select.return_value = ["backup_a"]
        mock_health = MagicMock()
        mock_health.get_health_map.return_value = {"backup_a": True}

        with patch.dict("sys.modules", {
            "routing_engine": mock_routing,
            "health_tracker": mock_health,
        }):
            result = _get_fallback_backends("primary", [], ide_source="cursor")

        mock_routing.select.assert_called_once_with("ide", {"backup_a": True})
        assert result == ["backup_a"]
