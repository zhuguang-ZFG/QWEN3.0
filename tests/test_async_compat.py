"""Tests for routes/async_compat.py — async helpers."""

import pytest

from routes.async_compat import maybe_await


class TestMaybeAwait:
    @pytest.mark.asyncio
    async def test_awaits_coroutine(self):
        async def coro():
            return 42

        assert await maybe_await(coro()) == 42

    @pytest.mark.asyncio
    async def test_returns_plain_value(self):
        assert await maybe_await(42) == 42

    @pytest.mark.asyncio
    async def test_returns_none(self):
        assert await maybe_await(None) is None
