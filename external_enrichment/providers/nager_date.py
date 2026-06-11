"""Nager.Date public holiday provider (offline tests with mock)."""
import time
from typing import Optional
from external_enrichment.schemas import EnrichmentResult


class NagerDateProvider:
    """Public holiday data from Nager.Date API."""

    def __init__(self, cache, rate_limiter):
        self.cache = cache
        self.rate_limiter = rate_limiter

    def get_holidays(self, country_code: str, year: int) -> Optional[EnrichmentResult]:
        """Get holidays for country/year. Returns cached or None on rate limit."""
        cache_key = f"holidays_{country_code}_{year}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        if not self.rate_limiter.allow("nager_date"):
            return None  # Rate limited, return None (fallback)

        # TODO: Actual API call would go here
        # For now, return mock data
        result = EnrichmentResult(
            provider="nager_date",
            data={"holidays": ["2026-01-01", "2026-12-25"]},
            cached=False,
            attribution="Public holiday data from Nager.Date API",
            timestamp=int(time.time()),
        )
        self.cache.set(cache_key, result)
        return result
