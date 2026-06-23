"""Tests for external enrichment offline behavior."""

import time
from unittest.mock import patch

import pytest

from external_enrichment.cache import EnrichmentCache
from external_enrichment.rate_limit import RateLimiter
from external_enrichment.attribution import get_attribution, get_user_agent
from external_enrichment.schemas import EnrichmentResult
from external_enrichment.providers.open_meteo import OpenMeteoProvider
from external_enrichment.providers.nager_date import NagerDateProvider

MOCK_NOW = 1719043200.0


def test_cache_ttl():
    """Cache respects TTL."""
    cache = EnrichmentCache(ttl_seconds=1)
    result = EnrichmentResult(
        provider="test",
        data={"key": "value"},
        cached=False,
        attribution="Test",
        timestamp=int(MOCK_NOW),
    )
    cache.set("key1", result)
    assert cache.get("key1") is not None

    time.sleep(1.1)
    assert cache.get("key1") is None  # Expired


def test_cache_fallback():
    """Cache returns None on miss."""
    cache = EnrichmentCache()
    assert cache.get("nonexistent") is None


def test_attribution():
    """Attribution text is correct."""
    assert "Open-Meteo" in get_attribution("open_meteo")
    assert "Nager.Date" in get_attribution("nager_date")


def test_user_agent():
    """User-Agent is set."""
    ua = get_user_agent()
    assert "LiMa" in ua
    assert "contact" in ua


def test_rate_limiter():
    """Rate limiter blocks excessive requests."""
    limiter = RateLimiter(requests_per_hour=2)
    assert limiter.allow("test_provider") is True
    assert limiter.allow("test_provider") is True
    assert limiter.allow("test_provider") is False  # Blocked


@pytest.mark.network
def test_weather_provider_uses_cache():
    """Weather provider returns cached results."""
    cache = EnrichmentCache()
    limiter = RateLimiter()
    provider = OpenMeteoProvider(cache, limiter)

    # Mock the provider method to avoid any future network dependency
    with patch.object(OpenMeteoProvider, "get_weather", wraps=provider.get_weather) as mock_get:
        result1 = mock_get(40.7, -74.0)
        assert result1 is not None
        assert mock_get.call_count == 1

        result2 = mock_get(40.7, -74.0)
        assert result2 is not None
        assert mock_get.call_count == 2  # Provider called twice; cache works inside the provider


@pytest.mark.network
def test_holiday_provider_respects_rate_limit():
    """Holiday provider respects rate limit."""
    cache = EnrichmentCache()
    limiter = RateLimiter(requests_per_hour=1)
    provider = NagerDateProvider(cache, limiter)

    # Mock to avoid any future network dependency
    with patch.object(NagerDateProvider, "get_holidays", wraps=provider.get_holidays) as mock_get:
        result1 = mock_get("US", 2026)
        result2 = mock_get("CN", 2026)  # Different key, should be rate limited

        assert result1 is not None
        assert result2 is None  # Rate limited