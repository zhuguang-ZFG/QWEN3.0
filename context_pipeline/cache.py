"""Context caching utilities for maximizing model prefix cache hits.

Google ADK pattern: stable system instructions at the FRONT of the context,
variable content (code context, session memory) at the END.
Same IDE+scenario combination produces identical prefix → cache hit.
"""

import hashlib
from dataclasses import dataclass


@dataclass
class CacheMetrics:
    """Track prefix caching effectiveness."""

    total_requests: int = 0
    cache_eligible: int = 0
    unique_prefixes: int = 0
    _prefix_hashes: set = None

    def __post_init__(self):
        if self._prefix_hashes is None:
            self._prefix_hashes = set()

    def record(self, prefix_hash: str) -> None:
        self.total_requests += 1
        self.cache_eligible += 1
        self._prefix_hashes.add(prefix_hash)
        self.unique_prefixes = len(self._prefix_hashes)

    @property
    def hit_rate_estimate(self) -> float:
        """Estimated cache hit rate (lower unique/total = better)."""
        if self.cache_eligible == 0:
            return 0.0
        return 1.0 - (self.unique_prefixes / self.cache_eligible)


_metrics = CacheMetrics()


def get_cache_metrics() -> CacheMetrics:
    return _metrics


def compute_stable_prefix(ide: str, scenario: str) -> str:
    """Compute deterministic stable prefix for a given IDE+scenario.

    Same IDE+scenario always produces the same prefix content,
    maximizing prefix cache hits across requests.
    """
    from prompt_engineering.layers import build_role_layer, build_skill_layer, build_quality_gate

    parts = [
        build_role_layer(ide, scenario),
        build_skill_layer(scenario),
        build_quality_gate(scenario),
    ]
    return "\n\n".join(parts)


def compute_prefix_hash(stable_prefix: str) -> str:
    """Hash the stable prefix for cache tracking."""
    return hashlib.sha256(stable_prefix.encode()).hexdigest()[:12]


def build_cached_prompt(
    ide: str,
    scenario: str,
    variable_content: str = "",
) -> tuple[str, str]:
    """Build prompt with stable prefix + variable suffix.

    Returns (full_prompt, prefix_hash) for cache tracking.
    """
    stable = compute_stable_prefix(ide, scenario)
    prefix_hash = compute_prefix_hash(stable)
    _metrics.record(prefix_hash)

    if variable_content:
        full = stable + "\n\n" + variable_content
    else:
        full = stable

    return full, prefix_hash
