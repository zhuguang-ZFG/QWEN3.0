"""OpenCode direct stream fast path tests."""

from __future__ import annotations

from unittest.mock import patch

import pytest


def test_resolve_opencode_backend_prefers_healthy_prefer():
    from routes.opencode_direct_stream import resolve_opencode_backend

    with patch("routes.opencode_direct_stream.health_tracker") as ht, patch(
        "routes.opencode_direct_stream._select_key", return_value=("key", None)
    ), patch("routes.opencode_direct_stream.BACKENDS", {"scnet_ds_flash": {"url": "x"}}):
        ht.is_cooled_down.return_value = False
        assert resolve_opencode_backend("scnet_ds_flash") == "scnet_ds_flash"


def test_stream_response_uses_prefer_without_speculative():
    import asyncio
    from routes.chat_stream import stream_response

    chunks: list[str] = []

    async def _fake_real_stream(*_a, **_k):
        yield "hello"

    with patch(
        "routes.chat_stream.real_stream_chunks_async", side_effect=_fake_real_stream
    ) as real_stream, patch(
        "routes.chat_stream.speculative_stream_chunks"
    ) as speculative:
        async for item in stream_response(
            "chat-1",
            "hi",
            False,
            messages=[{"role": "user", "content": "hi"}],
            prefer="scnet_ds_flash",
            has_tools=False,
        ):
            chunks.append(item)
        real_stream.assert_called_once()
        speculative.assert_not_called()

    assert any("hello" in c for c in chunks)
    assert any("[DONE]" in c for c in chunks)
