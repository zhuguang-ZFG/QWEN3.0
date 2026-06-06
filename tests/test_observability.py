"""Tests for observability events, metrics, and redaction guarantees."""
import pytest

from observability.events import (
    LiMaEvent,
    _hash_session,
    _make_request_id,
    backend_call_event,
    backend_error_event,
    key_pool_event,
    quality_result_event,
    request_end_event,
    request_start_event,
    route_decision_event,
    token_usage_event,
)
from observability.metrics import (
    get_fastest_growing_failure_class,
    get_metrics_snapshot,
    get_top_failing_backends,
    get_top_quality_backends,
    record,
    reset_metrics,
)


def setup_function():
    reset_metrics()



def test_event_defaults():
    e = LiMaEvent(event_type="test")
    assert e.event_type == "test"
    assert e.timestamp > 0
    assert len(e.request_id) == 16
    assert e.failure_class == ""
    assert e.quality_score == -1.0


def test_event_no_raw_secrets_in_field_names():
    """LiMaEvent has no field that could hold raw secrets."""
    fields = {f.name for f in LiMaEvent.__dataclass_fields__.values()}
    assert "api_key" not in fields
    assert "token" not in fields
    assert "cookie" not in fields
    assert "password" not in fields
    assert "prompt" not in fields


def test_request_start_event():
    e = request_start_event(request_id="abc123", session_id="sess1")
    assert e.event_type == "request_start"
    assert e.request_id == "abc123"
    assert e.session_id_hash != "sess1"
    assert len(e.session_id_hash) == 12


def test_request_end_event():
    e = request_end_event("req1", 150.5, True)
    assert e.event_type == "request_end"
    assert e.latency_ms == 150.5
    assert e.failure_class == ""


def test_request_end_event_failure():
    e = request_end_event("req1", 50.0, False)
    assert e.failure_class == "request_failed"


def test_backend_call_event():
    e = backend_call_event(
        "req1", "scnet_ds_flash", "coding_pool", session_id="s1", latency_ms=42.5
    )
    assert e.event_type == "backend_call"
    assert e.backend == "scnet_ds_flash"
    assert e.route_reason == "coding_pool"
    assert e.latency_ms == 42.5
    assert e.session_id_hash != "s1"


def test_backend_error_event():
    e = backend_error_event("req1", "groq_llama70b", "rate_limited", latency_ms=200.0)
    assert e.event_type == "backend_error"
    assert e.backend == "groq_llama70b"
    assert e.failure_class == "rate_limited"


def test_route_decision_event():
    e = route_decision_event("req1", "scnet_ds_flash", "reputation_top",
                             candidates=["scnet_ds_flash", "github_gpt4o", "cf_qwen_coder"] * 2)
    assert e.event_type == "route_decision"
    assert len(e.metadata["candidates"]) <= 5


def test_quality_result_event():
    e = quality_result_event("req1", "scnet_ds_flash", 0.9, True)
    assert e.event_type == "quality_result"
    assert e.quality_score == 0.9
    assert e.failure_class == ""


def test_quality_result_event_failure():
    e = quality_result_event("req1", "bad_backend", 0.2, False)
    assert e.failure_class == "quality_fail"


def test_key_pool_event():
    e = key_pool_event("groq", "exhausted", "all keys blocked")
    assert e.event_type == "key_pool_event"
    assert e.backend == "groq"
    assert "exhausted" in e.route_reason


def test_key_pool_event_redacts_secret_details():
    e = key_pool_event("groq", "cooldown", "token = Bearer abcdefghijklmnopqrstuvwxyz123456")
    assert "Bearer" not in str(e.metadata)
    assert "[REDACTED]" in str(e.metadata)


def test_event_metadata_redacts_sensitive_keys_and_values():
    e = LiMaEvent(
        event_type="test",
        metadata={
            "prompt": "private repo prompt",
            "safe": "token = Bearer abcdefghijklmnopqrstuvwxyz123456",
            "nested": {"cookie": "session=secret-cookie"},
        },
    )

    text = str(e.metadata)
    assert "private repo prompt" not in text
    assert "Bearer" not in text
    assert "secret-cookie" not in text
    assert text.count("[REDACTED]") >= 3


def test_token_usage_event():
    e = token_usage_event("scnet_ds_flash", 500, 200, "free")
    assert e.event_type == "token_usage"
    assert e.prompt_tokens == 500
    assert e.completion_tokens == 200
    assert e.cost_class == "free"


def test_hash_session_deterministic():
    assert _hash_session("hello") == _hash_session("hello")
    assert _hash_session("hello") != _hash_session("world")


def test_hash_session_empty():
    assert _hash_session("") == ""



def test_record_request_start_increments_total():
    record(request_start_event("r1"))
    snapshot = get_metrics_snapshot()
    assert snapshot["total_requests"] == 1


def test_record_backend_call_tracks_success():
    record(backend_call_event("r1", "scnet_ds_flash", "coding"))
    snapshot = get_metrics_snapshot()
    assert snapshot["backends"]["scnet_ds_flash"]["success"] == 1


def test_record_backend_error_tracks_failure_class():
    record(backend_error_event("r1", "groq", "rate_limited"))
    snapshot = get_metrics_snapshot()
    assert snapshot["backends"]["groq"]["failure"] == 1
    assert snapshot["failure_class_counts"]["rate_limited"] == 1


def test_record_latency_tracks_percentiles():
    for i in range(10):
        e = backend_call_event(f"r{i}", "test_backend", "test")
        e.latency_ms = float(i * 10 + 10)  # 10, 20, ..., 100
        record(e)
    snapshot = get_metrics_snapshot()
    stats = snapshot["backends"]["test_backend"]
    assert abs(stats["avg_latency_ms"] - 55.0) < 1.0
    assert stats["p50_latency_ms"] >= 50
    assert stats["p95_latency_ms"] >= 80


def test_record_quality_tracks_avg():
    for score in [0.5, 0.7, 0.9, 0.3]:
        record(quality_result_event("r", "test_backend", score, score >= 0.5))
    snapshot = get_metrics_snapshot()
    avg = snapshot["backends"]["test_backend"]["avg_quality_score"]
    assert 0.5 <= avg <= 0.7


def test_record_token_usage_accumulates():
    record(token_usage_event("scnet", 100, 50, "free"))
    record(token_usage_event("scnet", 200, 100, "free"))
    snapshot = get_metrics_snapshot()
    stats = snapshot["backends"]["scnet"]
    assert stats["prompt_tokens"] == 300
    assert stats["completion_tokens"] == 150
    assert stats["token_requests"] == 2


def test_reset_metrics_clears_all():
    record(request_start_event("r1"))
    record(backend_error_event("r1", "bad", "timeout"))
    reset_metrics()
    snapshot = get_metrics_snapshot()
    assert snapshot["total_requests"] == 0
    assert snapshot["backends"] == {}


def test_snapshot_isolation():
    """Metric snapshots reflect state at capture time."""
    record(backend_call_event("r1", "a", "test"))
    snap1 = get_metrics_snapshot()
    assert snap1["backends"]["a"]["success"] == 1
    record(backend_call_event("r2", "b", "test"))
    snap2 = get_metrics_snapshot()
    assert "b" in snap2["backends"]
    assert snap1.get("backends", {}).get("b") is None


def test_get_top_failing_backends():
    for b in ["a", "b", "c"]:
        for _ in range({"a": 5, "b": 3, "c": 1}[b]):
            record(backend_error_event("r", b, "timeout"))
    top = get_top_failing_backends(2)
    assert top[0][0] == "a"
    assert top[0][1] == 5
    assert len(top) == 2


def test_get_top_quality_backends():
    for b, scores in [("good", [0.9, 0.95, 0.92]), ("bad", [0.3, 0.4, 0.35]), ("ok", [0.6, 0.7])]:
        for s in scores:
            record(quality_result_event("r", b, s, s >= 0.5))
    top = get_top_quality_backends(3)
    assert top[0][0] == "good"
    assert top[0][1] >= 0.9


def test_get_fastest_growing_failure_class():
    for cls, count in [("rate_limited", 10), ("auth_expired", 3), ("timeout", 1)]:
        for _ in range(count):
            record(backend_error_event("r", "x", cls))
    top = get_fastest_growing_failure_class(3)
    assert top[0][0] == "rate_limited"
    assert top[0][1] == 10



def test_snapshot_never_contains_raw_key():
    snapshot = get_metrics_snapshot()
    text = str(snapshot)
    assert "sk-" not in text


def test_snapshot_never_contains_raw_prompt():
    record(backend_call_event("r1", "test", "coding", session_id="user_session_123"))
    snapshot = get_metrics_snapshot()
    text = str(snapshot)
    assert "user_session_123" not in text


def test_session_ids_are_hashed():
    e1 = backend_call_event("r1", "test", "", session_id="real_session_abc")
    e2 = backend_call_event("r2", "test", "", session_id="real_session_abc")
    assert e1.session_id_hash == e2.session_id_hash
    assert "real_session_abc" not in e1.session_id_hash



def test_event_type_counts_accurate():
    for _ in range(3):
        record(request_start_event("r"))
    for _ in range(5):
        record(backend_call_event("r", "b", "t"))
    for _ in range(2):
        record(backend_error_event("r", "b", "timeout"))

    snapshot = get_metrics_snapshot()
    assert snapshot["event_type_counts"]["request_start"] == 3
    assert snapshot["event_type_counts"]["backend_call"] == 5
    assert snapshot["event_type_counts"]["backend_error"] == 2
