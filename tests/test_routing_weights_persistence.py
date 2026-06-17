"""Tests for routing_weights persistence and learning behavior."""

import json

import pytest


@pytest.fixture(autouse=True)
def _isolated_weights(tmp_path, monkeypatch):
    """Use a temp file for each test to avoid cross-test contamination."""
    weights_file = tmp_path / "weights.json"
    monkeypatch.setattr(
        "context_pipeline.routing_weights.WEIGHTS_PATH",
        weights_file,
    )
    yield weights_file


def _fresh():
    """Create a fresh RoutingWeights instance (bypass singleton)."""
    from context_pipeline.routing_weights import RoutingWeights

    return RoutingWeights()


def test_default_weight():
    rw = _fresh()
    assert rw.get_weight("backend_a", "coding") == 1.0


def test_record_success_increases_weight():
    rw = _fresh()
    rw.record_success("backend_a", "coding")
    w = rw.get_weight("backend_a", "coding")
    assert w > 1.0


def test_record_failure_decreases_weight():
    rw = _fresh()
    rw.record_failure("backend_a", "coding")
    w = rw.get_weight("backend_a", "coding")
    assert w < 1.0


def test_success_failure_cycle():
    rw = _fresh()
    rw.record_success("backend_a", "coding")
    rw.record_success("backend_a", "coding")
    rw.record_failure("backend_a", "coding")
    stats = rw.get_stats("backend_a", "coding")
    assert stats["successes"] == 2
    assert stats["failures"] == 1
    assert stats["success_rate"] == pytest.approx(2 / 3)


def test_rank_backends_orders_by_weight(tmp_path, monkeypatch):
    rw = _fresh()
    # backend_b gets more successes → higher weight
    for _ in range(5):
        rw.record_success("backend_b", "coding")
    rw.record_failure("backend_a", "coding")

    ranked = rw.rank_backends(["backend_a", "backend_b"], "coding")
    assert ranked[0] == "backend_b"


def test_weight_bounds():
    rw = _fresh()
    # Upper bound
    for _ in range(100):
        rw.record_success("hot_backend", "chat")
    assert rw.get_weight("hot_backend", "chat") <= 2.0

    # Lower bound
    for _ in range(100):
        rw.record_failure("cold_backend", "chat")
    assert rw.get_weight("cold_backend", "chat") >= 0.1


def test_persistence_round_trip(_isolated_weights):
    # Write weights
    rw1 = _fresh()
    rw1.record_success("persist_backend", "coding")
    rw1.record_success("persist_backend", "coding")
    rw1.record_failure("persist_backend", "coding")
    w1 = rw1.get_weight("persist_backend", "coding")

    # Verify file exists
    assert _isolated_weights.exists()
    data = json.loads(_isolated_weights.read_text(encoding="utf-8"))
    assert "persist_backend:coding" in data

    # Reload from same file
    rw2 = _fresh()
    w2 = rw2.get_weight("persist_backend", "coding")
    assert w2 == pytest.approx(w1)

    stats = rw2.get_stats("persist_backend", "coding")
    assert stats["successes"] == 2
    assert stats["failures"] == 1


def test_no_persistence_when_no_data(_isolated_weights):
    _fresh()
    # No record_* called → file not created
    assert not _isolated_weights.exists()


def test_corrupt_file_handled():
    """Corrupt weights file should not crash initialization."""
    from context_pipeline.routing_weights import RoutingWeights, WEIGHTS_PATH

    WEIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    WEIGHTS_PATH.write_text("NOT JSON {{{", encoding="utf-8")
    rw = RoutingWeights()
    assert rw.get_weight("any", "any") == 1.0
