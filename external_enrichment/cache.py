"""Cache with TTL for enrichment results."""
import time
from typing import Optional
from external_enrichment.schemas import EnrichmentResult


class EnrichmentCache:
    """In-memory cache for enrichment results."""

    def __init__(self, ttl_seconds: int = 3600):
        self.ttl_seconds = ttl_seconds
        self._cache: dict[str, tuple[EnrichmentResult, int]] = {}

    def get(self, key: str) -> Optional[EnrichmentResult]:
        """Get cached result if not expired."""
        if key not in self._cache:
            return None
        result, timestamp = self._cache[key]
        if time.time() - timestamp > self.ttl_seconds:
            del self._cache[key]
            return None
        return result

    def set(self, key: str, result: EnrichmentResult):
        """Cache a result."""
        self._cache[key] = (result, int(time.time()))

    def clear(self):
        """Clear all cached results."""
        self._cache.clear()
