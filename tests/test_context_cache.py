"""Tests for context_pipeline/cache.py — prefix cache metrics."""

from context_pipeline.cache import CacheMetrics, get_cache_metrics, compute_stable_prefix, compute_prefix_hash


class TestCacheMetrics:
    def test_initial_values(self):
        m = CacheMetrics()
        assert m.total_requests == 0
        assert m.hit_rate_estimate == 0.0

    def test_record_increments(self):
        m = CacheMetrics()
        m.record("hash1")
        assert m.total_requests == 1
        assert m.unique_prefixes == 1

    def test_duplicate_prefix(self):
        m = CacheMetrics()
        m.record("hash1")
        m.record("hash1")
        assert m.total_requests == 2
        assert m.unique_prefixes == 1
        assert m.hit_rate_estimate == 0.5


class TestStablePrefix:
    def test_returns_string(self):
        result = compute_stable_prefix("vscode", "chat")
        assert isinstance(result, str)


class TestPrefixHash:
    def test_deterministic(self):
        h1 = compute_prefix_hash("stable")
        h2 = compute_prefix_hash("stable")
        assert h1 == h2


class TestGetCacheMetrics:
    def test_returns_metrics(self):
        metrics = get_cache_metrics()
        assert isinstance(metrics, CacheMetrics)
