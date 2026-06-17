"""Open-Meteo weather provider (offline tests with mock)."""

import time
from typing import Optional
from external_enrichment.schemas import EnrichmentResult


class OpenMeteoProvider:
    """Weather data from Open-Meteo.com."""

    def __init__(self, cache, rate_limiter):
        self.cache = cache
        self.rate_limiter = rate_limiter

    def get_weather(self, lat: float, lon: float) -> Optional[EnrichmentResult]:
        """Get weather for coordinates. Returns cached or None on rate limit."""
        cache_key = f"weather_{lat}_{lon}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        if not self.rate_limiter.allow("open_meteo"):
            return None  # Rate limited, return None (fallback)

        # TODO: Actual API call would go here
        # For now, return mock data
        result = EnrichmentResult(
            provider="open_meteo",
            data={"temperature": 20, "condition": "sunny"},
            cached=False,
            attribution="Weather data from Open-Meteo.com",
            timestamp=int(time.time()),
        )
        self.cache.set(cache_key, result)
        return result
