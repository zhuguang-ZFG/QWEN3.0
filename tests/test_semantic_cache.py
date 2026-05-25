"""Semantic cache observability (P1.1)."""

import semantic_cache


def test_put_logs_db_write_failure_and_increments_counter(monkeypatch, caplog):
    cache = semantic_cache.SemanticCache(max_size=10, ttl=60)

    class BrokenDb:
        def execute(self, *args, **kwargs):
            raise RuntimeError("disk full")

        def commit(self):
            raise RuntimeError("disk full")

    cache._db = BrokenDb()
    monkeypatch.setattr(semantic_cache, "_log", semantic_cache._log)

    with caplog.at_level("WARNING"):
        cache.put("abc123", '{"ok":true}')

    assert cache._db_write_errors == 1
    assert any("semantic_cache db write failed" in r.message for r in caplog.records)
