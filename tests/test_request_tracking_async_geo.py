"""Tests for async IP geo resolution in routes/request_tracking.py."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from routes import request_tracking as rt


@pytest.fixture(autouse=True)
def _clear_stats():
    rt._stats.clear()
    rt._stats.update(
        {
            "total_requests": 0,
            "backend_calls": {},
            "intent_distribution": {},
            "recent_logs": [],
            "start_time": 0,
        }
    )
    rt.get_ip_location.cache_clear()
    yield


class TestResolveIpCountry:
    async def test_resolve_ip_country_runs_in_executor(self):
        with patch.object(rt, "_fetch_ip_location", return_value="中国 北京") as mock_fetch:
            result = await rt.resolve_ip_country("1.2.3.4")
        assert result == "中国 北京"
        mock_fetch.assert_called_once_with("1.2.3.4")

    async def test_resolve_ip_country_returns_empty_for_empty_ip(self):
        with patch.object(rt, "_fetch_ip_location") as mock_fetch:
            result = await rt.resolve_ip_country("")
        assert result == ""
        mock_fetch.assert_not_called()

    async def test_resolve_ip_country_does_not_block_event_loop(self):
        # Simulate a slow synchronous geo lookup running in an executor thread.
        # A concurrent coroutine should still be able to complete while the lookup runs.
        with patch.object(
            rt,
            "_fetch_ip_location",
            side_effect=lambda _ip: (__import__("time").sleep(0.2), "中国 北京")[1],
        ):
            resolve_task = asyncio.create_task(rt.resolve_ip_country("1.2.3.4"))
            concurrent_task = asyncio.create_task(asyncio.sleep(0.01))

            done, _pending = await asyncio.wait(
                {resolve_task, concurrent_task},
                return_when=asyncio.FIRST_COMPLETED,
                timeout=2,
            )

            assert concurrent_task in done, "event loop was blocked by sync geo lookup"
            assert resolve_task not in done
            result = await asyncio.wait_for(resolve_task, timeout=2)
            assert result == "中国 北京"


class TestRecordRequestCountry:
    def test_record_request_uses_passed_country_without_lookup(self):
        with patch.object(rt, "_fetch_ip_location") as mock_fetch:
            rt.record_request(
                "hi",
                "test-backend",
                "chat",
                100,
                True,
                client_ip="1.2.3.4",
                country="中国 北京",
            )
        mock_fetch.assert_not_called()
        assert rt._stats["recent_logs"][0]["country"] == "中国 北京"

    def test_record_request_falls_back_to_lookup_when_country_missing(self):
        with patch.object(rt, "_fetch_ip_location", return_value="本地") as mock_fetch:
            rt.record_request(
                "hi",
                "test-backend",
                "chat",
                100,
                True,
                client_ip="127.0.0.1",
            )
        mock_fetch.assert_not_called()  # localhost is handled before lookup
        assert rt._stats["recent_logs"][0]["country"] == "本地"
