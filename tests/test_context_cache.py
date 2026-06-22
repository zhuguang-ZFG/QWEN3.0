"""Tests for context_pipeline/cache.py — prefix cache metrics."""

from context_pipeline.cache import CacheMetrics, get_cache_metrics


class TestCacheMetrics:
    def test_initial_state(self):
        m = CacheMetrics()
        assert m.total_requests == 0
        assert m.cache_eligible == 0
        assert m.unique_prefixes == 0
        assert m.hit_rate_estimate == 0.0

    def test_record_increases_counters(self):
        m = CacheMetrics()
        m.record("hash1")
        assert m.total_requests == 1
        assert m.cache_eligible == 1
        assert m.unique_prefixes == 1

    def test_duplicate_hash(self):
        m = CacheMetrics()
        m.record("same")
        m.record("same")
        assert m.total_requests == 2
        assert m.unique_prefixes == 1  # same hash

    def test_different_hashes(self):
        m = CacheMetrics()
        m.record("a")
        m.record("b")
        m.record("c")
        assert m.unique_prefixes == 3

    def test_hit_rate_estimate(self):
        m = CacheMetrics()
        m.record("a")
        m.record("a")
        assert m.hit_rate_estimate == 0.5  # 1 unique / 2 total = 0.5

    def test_perfect_hit_rate(self):
        m = CacheMetrics()
        for _ in range(10):
            m.record("same")
        assert m.hit_rate_estimate == 0.9  # 1/10 = 0.1 unique ratio

    def test_zero_hit_rate(self):
        m = CacheMetrics()
        for i in range(5):
            m.record(f"h{i}")
        assert m.hit_rate_estimate == 0.0  # all unique


class TestGetCacheMetrics:
    def test_returns_metrics_instance(self):
        m = get_cache_metrics()
        assert isinstance(m, CacheMetrics)
