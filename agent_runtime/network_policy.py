"""Network/provider execution policy with domain allowlist and rate limits."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


DEFAULT_DOMAIN_ALLOWLIST: frozenset[str] = frozenset()
DEFAULT_MAX_REQUESTS_PER_MINUTE: int = 10


@dataclass
class NetworkDecision:
    allowed: bool
    reason: str = ""


@dataclass
class NetworkPolicy:
    domain_allowlist: frozenset[str] = DEFAULT_DOMAIN_ALLOWLIST
    max_requests_per_minute: int = DEFAULT_MAX_REQUESTS_PER_MINUTE
    _request_timestamps: list[float] = field(default_factory=list)

    def check_request(self, url: str) -> NetworkDecision:
        host = self._extract_host(url)
        if not host:
            return NetworkDecision(allowed=False, reason="invalid url")

        if not self.domain_allowlist:
            return NetworkDecision(allowed=False, reason="no domains allowlisted")

        if not any(_host_matches(host, domain) for domain in self.domain_allowlist):
            return NetworkDecision(
                allowed=False,
                reason=f"domain '{host}' not in allowlist",
            )

        now = time.time()
        self._request_timestamps = [
            timestamp for timestamp in self._request_timestamps if now - timestamp < 60
        ]
        if (
            self.max_requests_per_minute <= 0
            or len(self._request_timestamps) >= self.max_requests_per_minute
        ):
            return NetworkDecision(allowed=False, reason="rate limit exceeded")

        self._request_timestamps.append(now)
        return NetworkDecision(allowed=True, reason="ok")

    def _extract_host(self, url: str) -> str:
        try:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                return ""
            return parsed.hostname or ""
        except Exception:
            return ""


def build_default_policy(allowlist: frozenset[str] | None = None) -> NetworkPolicy:
    return NetworkPolicy(domain_allowlist=allowlist or DEFAULT_DOMAIN_ALLOWLIST)


def _host_matches(host: str, domain: str) -> bool:
    host = host.lower().rstrip(".")
    domain = domain.lower().rstrip(".")
    return host == domain or host.endswith(f".{domain}")
