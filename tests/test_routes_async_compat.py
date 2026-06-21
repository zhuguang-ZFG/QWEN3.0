"""Tests for routes.async_compat helpers."""

from __future__ import annotations

from routes.async_compat import maybe_await


async def test_maybe_await_returns_plain_value():
    assert await maybe_await(42) == 42


async def test_maybe_await_awaits_coroutine():
    async def coro():
        return "done"

    assert await maybe_await(coro()) == "done"
