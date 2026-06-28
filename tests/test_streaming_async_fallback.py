"""Tests for streaming.py async fallback path."""

from __future__ import annotations

import asyncio
from typing import AsyncIterator

import pytest

from streaming import _async_fallback_to_api, bridge_stream_async


async def _empty_stream(*_args, **_kwargs) -> AsyncIterator[str]:
    return
    yield  # make it an async generator


async def _failing_stream(*_args, **_kwargs) -> AsyncIterator[str]:
    raise RuntimeError("stream exploded")
    yield


async def _api_call(*_args, **_kwargs) -> str:
    return "fallback answer"


async def _api_call_error(*_args, **_kwargs) -> str:
    raise RuntimeError("api exploded")


async def _api_call_err_prefix(*_args, **_kwargs) -> str:
    return "[ERR] bad things"


class TestAsyncFallback:
    async def test_fallback_yields_api_result_when_stream_empty(self):
        chunks = [
            chunk
            async for chunk in bridge_stream_async(
                "test-backend",
                [{"role": "user", "content": "hi"}],
                128,
                "unknown",
                call_stream_async_fn=_empty_stream,
                call_api_async_fn=_api_call,
            )
        ]
        assert chunks == ["fallback answer"]

    async def test_fallback_skips_err_prefixed_api_result(self):
        chunks = [
            chunk
            async for chunk in bridge_stream_async(
                "test-backend",
                [{"role": "user", "content": "hi"}],
                128,
                "unknown",
                call_stream_async_fn=_empty_stream,
                call_api_async_fn=_api_call_err_prefix,
            )
        ]
        assert chunks == []

    async def test_fallback_api_exception_isolated(self):
        chunks = [
            chunk
            async for chunk in bridge_stream_async(
                "test-backend",
                [{"role": "user", "content": "hi"}],
                128,
                "unknown",
                call_stream_async_fn=_empty_stream,
                call_api_async_fn=_api_call_error,
            )
        ]
        assert chunks == []

    async def test_stream_exception_triggers_fallback(self):
        chunks = [
            chunk
            async for chunk in bridge_stream_async(
                "test-backend",
                [{"role": "user", "content": "hi"}],
                128,
                "unknown",
                call_stream_async_fn=_failing_stream,
                call_api_async_fn=_api_call,
            )
        ]
        assert chunks == ["fallback answer"]

    async def test_direct_fallback_helper_yields_text(self):
        chunks = [
            chunk
            async for chunk in _async_fallback_to_api(
                "test-backend",
                [{"role": "user", "content": "hi"}],
                128,
                "unknown",
                call_api_async_fn=_api_call,
            )
        ]
        assert chunks == ["fallback answer"]

    async def test_direct_fallback_helper_suppresses_exception(self):
        chunks = [
            chunk
            async for chunk in _async_fallback_to_api(
                "test-backend",
                [{"role": "user", "content": "hi"}],
                128,
                "unknown",
                call_api_async_fn=_api_call_error,
            )
        ]
        assert chunks == []
