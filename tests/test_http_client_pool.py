"""Tests for httpx client connection-pool reuse (AUDIT-8-P4)."""

from __future__ import annotations

import httpx
import pytest

from http_request_builder import client as client_mod


@pytest.fixture(autouse=True)
def _reset_cache():
    client_mod.reset_client_cache_for_tests()
    yield
    client_mod.reset_client_cache_for_tests()


def test_same_backend_reuses_client():
    """Same backend → same cached httpx.Client instance."""
    w1 = client_mod._build_client("scnet_local", 10)
    w2 = client_mod._build_client("scnet_local", 10)
    with w1 as c1, w2 as c2:
        assert c1 is c2  # reused, not rebuilt


def test_different_backends_distinct_clients():
    """Different backends → distinct cached clients."""
    with client_mod._build_client("scnet_local", 10) as c1:
        with client_mod._build_client("longcat_chat", 10) as c2:
            assert c1 is not c2


def test_noop_wrapper_does_not_close_client():
    """Exiting the `with` block must NOT close the shared client."""
    wrapper = client_mod._build_client("scnet_local", 10)
    with wrapper as c:
        assert not c.is_closed
    # after context exit, the cached client must remain open for reuse
    assert not c.is_closed
    # and a subsequent build returns the same still-open client
    with client_mod._build_client("scnet_local", 10) as c2:
        assert c2 is c
        assert not c2.is_closed


def test_invalidate_client_cache_drops_and_closes():
    """invalidate_client_cache closes and removes the cached client."""
    with client_mod._build_client("scnet_local", 10) as c:
        assert not c.is_closed
    client_mod.invalidate_client_cache("scnet_local")
    assert c.is_closed
    # next build creates a fresh client
    with client_mod._build_client("scnet_local", 10) as c2:
        assert c2 is not c
        assert not c2.is_closed


def test_invalidate_all_clients():
    """invalidate_client_cache() with no arg drops every cached client."""
    with client_mod._build_client("scnet_local", 10) as c1:
        pass
    with client_mod._build_client("longcat_chat", 10) as c2:
        pass
    client_mod.invalidate_client_cache()
    assert c1.is_closed
    assert c2.is_closed


def test_async_same_backend_reuses_client():
    """Async: same backend → same cached AsyncClient instance."""

    async def _run():
        w1 = client_mod._build_async_client("scnet_local", 10)
        w2 = client_mod._build_async_client("scnet_local", 10)
        async with w1 as c1:
            async with w2 as c2:
                assert c1 is c2
        await client_mod.aclose_all_clients()

    import asyncio

    asyncio.run(_run())


def test_async_noop_wrapper_does_not_close():
    """Async: exiting `async with` must NOT close the shared client."""

    async def _run():
        wrapper = client_mod._build_async_client("scnet_local", 10)
        async with wrapper as c:
            assert not c.is_closed
        assert not c.is_closed  # still open after context exit
        await client_mod.aclose_all_clients()
        assert c.is_closed  # closed only on explicit shutdown

    import asyncio

    asyncio.run(_run())
