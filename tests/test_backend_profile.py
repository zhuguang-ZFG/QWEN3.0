"""Tests for backend_profile.py — performance profiling module."""

import os
import tempfile

# Set test DB path
os.environ["LIMA_BACKEND_PROFILE_DB"] = os.path.join(tempfile.gettempdir(), "test_profiles.db")

import backend_profile as bp


def test_record_request_success():
    bp._profiles.clear()
    bp.record_request("test_backend", 100.0, True, "coding", 500)
    p = bp.get_profile("test_backend")
    assert p.successes == 1
    assert p.failures == 0
    assert p.total_requests == 1
    assert p.latencies == [100.0]
    assert p.response_lengths == [500]
    assert p.scenario_successes == {"coding": 1}


def test_record_request_failure():
    bp._profiles.clear()
    bp.record_request("test_backend", 200.0, False, "chat", 0)
    p = bp.get_profile("test_backend")
    assert p.successes == 0
    assert p.failures == 1
    assert p.scenario_failures == {"chat": 1}


def test_composite_score():
    bp._profiles.clear()
    # Perfect backend: fast, high success, long responses
    bp.record_request("fast_good", 50.0, True, "coding", 1000)
    bp.record_request("fast_good", 60.0, True, "coding", 800)
    # Slow bad backend
    bp.record_request("slow_bad", 5000.0, False, "chat", 0)
    bp.record_request("slow_bad", 4000.0, True, "chat", 50)

    fast_score = bp.get_profile("fast_good").composite_score()
    slow_score = bp.get_profile("slow_bad").composite_score()
    assert fast_score > slow_score, f"fast={fast_score} should > slow={slow_score}"


def test_sliding_window():
    bp._profiles.clear()
    # Add 60 requests to trigger window trimming
    for i in range(60):
        bp.record_request("window_test", float(i), i % 3 != 0, "coding", 100)
    p = bp.get_profile("window_test")
    assert len(p.latencies) <= 50, f"latencies should be trimmed to 50, got {len(p.latencies)}"
    assert len(p.response_lengths) <= 20, f"response_lengths should be trimmed to 20"


def test_get_top_backends():
    bp._profiles.clear()
    bp.record_request("good", 100.0, True, "coding", 800)
    bp.record_request("medium", 500.0, True, "coding", 400)
    bp.record_request("bad", 5000.0, False, "chat", 50)
    top = bp.get_top_backends("coding", 2)
    assert "good" in top
    assert "medium" in top
    assert "bad" not in top


def test_persistence():
    bp._profiles.clear()
    bp.record_request("persist_test", 200.0, True, "coding", 300)
    bp.save_profiles()
    bp._profiles.clear()
    loaded = bp.load_profiles()
    assert loaded >= 1
    p = bp.get_profile("persist_test")
    assert p.successes == 1
    assert p.latencies == [200.0]


def test_best_worst_scenarios():
    bp._profiles.clear()
    # coding: 9 success, 1 failure
    for _ in range(9):
        bp.record_request("scenario_test", 100.0, True, "coding", 500)
    bp.record_request("scenario_test", 100.0, False, "coding", 0)
    # chat: 1 success, 9 failures
    for _ in range(9):
        bp.record_request("scenario_test", 100.0, False, "chat", 0)
    bp.record_request("scenario_test", 100.0, True, "chat", 500)

    p = bp.get_profile("scenario_test")
    assert "coding" in p.best_scenarios
    assert "chat" in p.worst_scenarios
