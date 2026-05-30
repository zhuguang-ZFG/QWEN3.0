"""Tests for the closed-loop routing architecture."""

from __future__ import annotations

import os
import sys
import tempfile


sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ─── Request Store tests ──────────────────────────────────────────────


class TestRequestStore:
    def _make_store(self):
        from routing_loop.request_store import RequestStore
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = f.name
        return RequestStore(db_path=path)

    def test_log_and_read(self):
        store = self._make_store()
        store.log_request(
            request_id="test-1", scenario="coding",
            message_length=100, code_ratio=0.5,
            feature_vector=[0.1] * 12, backend="groq_llama70b",
            success=True, latency_ms=500.0,
        )
        data = store.get_training_data(since_hours=1)
        assert len(data) == 1
        assert data[0].backend == "groq_llama70b"
        assert data[0].success is True
        assert data[0].feature_vector is not None
        assert len(data[0].feature_vector) == 12
        store.close()
        os.unlink(store._db_path)

    def test_backend_stats(self):
        store = self._make_store()
        for i in range(10):
            store.log_request(
                backend="a", scenario="coding", success=(i < 7),
                latency_ms=100 + i * 10,
            )
        stats = store.get_backend_stats("a", "coding")
        assert stats["total"] == 10
        assert stats["successes"] == 7
        assert stats["success_rate"] == 0.7
        store.close()
        os.unlink(store._db_path)

    def test_get_recent_features(self):
        store = self._make_store()
        for i in range(5):
            store.log_request(
                feature_vector=[float(i)] * 12,
                backend="x", scenario="chat", success=True,
            )
        features = store.get_recent_features(n=3)
        assert len(features) == 3
        store.close()
        os.unlink(store._db_path)

    def test_count(self):
        store = self._make_store()
        assert store.count() == 0
        store.log_request(backend="a", success=True)
        store.log_request(backend="b", success=False)
        assert store.count() == 2
        store.close()
        os.unlink(store._db_path)


# ─── Feedback Bridge tests ────────────────────────────────────────────


class TestFeedbackBridge:
    def test_on_request_complete(self):
        from routing_loop.request_store import RequestStore
        import routing_loop.request_store as rs_mod
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = f.name

        store = RequestStore(db_path=path)
        rs_mod._store = store  # inject test store

        try:
            from routing_loop.feedback_bridge import on_request_complete
            on_request_complete(
                request_id="test-bridge",
                scenario="coding",
                messages=[{"role": "user", "content": "fix this bug in routing_engine.py"}],
                backend="scnet_ds_flash",
                success=True,
                latency_ms=800.0,
            )
            assert store.count() == 1
            record = store.get_training_data(since_hours=1)[0]
            assert record.backend == "scnet_ds_flash"
            assert record.scenario == "coding"
            assert record.code_ratio >= 0  # no code fences in test message
            assert record.message_length > 0
        finally:
            store.close()
            os.unlink(path)
            rs_mod._store = None


# ─── Loop Closer tests ────────────────────────────────────────────────


class TestLoopCloser:
    def test_close_loop_with_empty_store(self, tmp_path):
        from routing_loop.request_store import RequestStore
        import routing_loop.request_store as rs_mod
        from routing_loop.loop_closer import close_loop

        store = RequestStore(db_path=str(tmp_path / "request_log.db"))
        rs_mod._store = store
        try:
            result = close_loop()
            assert "store_count" in result
            assert result["training"] is False  # not enough data
        finally:
            store.close()
            rs_mod._store = None

    def test_close_loop_with_data(self):
        from routing_loop.request_store import RequestStore
        import routing_loop.request_store as rs_mod
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = f.name

        store = RequestStore(db_path=path)
        rs_mod._store = store

        try:
            # Insert enough data to trigger training
            backends = ["a", "b", "c"]
            for i in range(50):
                store.log_request(
                    feature_vector=[float(i % 10) / 10] * 12,
                    backend=backends[i % 3],
                    scenario="coding" if i % 2 == 0 else "chat",
                    success=(i % 4 != 0),
                    latency_ms=100 + i * 20,
                )

            from routing_loop.loop_closer import close_loop
            result = close_loop()
            assert result["store_count"] == 50
            assert result["training"] is True
            assert result["training_samples"] > 0
        finally:
            store.close()
            os.unlink(path)
            rs_mod._store = None
