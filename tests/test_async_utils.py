"""Tests for async_utils.run_coro_sync — shared sync/async bridge."""

from __future__ import annotations

import pytest

from async_utils import run_coro_sync


async def _sample_coro(value: int) -> int:
    return value * 2


def test_run_coro_sync_in_sync_context():
    """Bridge works when no event loop is running."""
    assert run_coro_sync(_sample_coro(21)) == 42


@pytest.mark.asyncio
async def test_run_coro_sync_in_async_context():
    """Bridge works when an event loop is already running."""
    assert run_coro_sync(_sample_coro(21)) == 42
