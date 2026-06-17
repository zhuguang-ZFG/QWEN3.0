"""Rate limiting for enrichment providers."""

import time
from collections import defaultdict


class RateLimiter:
    """Simple token bucket rate limiter."""

    def __init__(self, requests_per_hour: int = 100):
        self.requests_per_hour = requests_per_hour
        self.tokens = requests_per_hour
        self.last_refill = time.time()
        self._provider_calls: defaultdict[str, list[float]] = defaultdict(list)

    def allow(self, provider: str) -> bool:
        """Check if request is allowed under rate limit."""
        now = time.time()
        # Clean old entries (older than 1 hour)
        cutoff = now - 3600
        self._provider_calls[provider] = [ts for ts in self._provider_calls[provider] if ts > cutoff]

        if len(self._provider_calls[provider]) >= self.requests_per_hour:
            return False

        self._provider_calls[provider].append(now)
        return True
