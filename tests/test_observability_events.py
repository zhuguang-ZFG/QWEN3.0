"""Tests for observability/events.py — LiMaEvent model and sanitization."""

from observability.events import (
    LiMaEvent,
    _hash_session,
    _make_request_id,
    request_start_event,
    request_end_event,
    backend_call_event,
    backend_error_event,
    route_decision_event,
    quality_result_event,
    key_pool_event,
    token_usage_event,
)


class TestHashSession:
    def test_empty_string(self):
        assert _hash_session("") == ""

    def test_consistent_hash(self):
        h1 = _hash_session("session-1")
        h2 = _hash_session("session-1")
        assert h1 == h2

    def test_different_sessions_different_hash(self):
        assert _hash_session("a") != _hash_session("b")

    def test_returns_12_chars(self):
        assert len(_hash_session("test-session")) == 12


class TestMakeRequestId:
    def test_returns_string(self):
        rid = _make_request_id()
        assert isinstance(rid, str)
        assert len(rid) == 16

    def test_unique_ids(self):
        assert _make_request_id() != _make_request_id()


class TestLiMaEvent:
    def test_default_values(self):
        event = LiMaEvent(event_type="request_start")
        assert event.event_type == "request_start"
        assert event.backend == ""
        assert event.latency_ms == 0.0
        assert event.prompt_tokens == 0

    def test_auto_generates_request_id(self):
        event = LiMaEvent(event_type="test")
        assert len(event.request_id) == 16

    def test_auto_generates_timestamp(self):
        event = LiMaEvent(event_type="test")
        assert event.timestamp > 0

    def test_custom_values(self):
        event = LiMaEvent(event_type="request_complete", backend="groq", latency_ms=150, prompt_tokens=100)
        assert event.backend == "groq"
        assert event.latency_ms == 150
        assert event.prompt_tokens == 100

    def test_session_hash(self):
        event = LiMaEvent(event_type="test", session_id_hash="abc123")
        assert event.session_id_hash == "abc123"

    def test_route_reason(self):
        event = LiMaEvent(event_type="test", route_reason="sticky session")
        assert event.route_reason == "sticky session"


# -- event factory coverage from former tests/test_observability.py ---------------


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
    e = backend_call_event("req1", "scnet_ds_flash", "coding_pool", session_id="s1", latency_ms=42.5)
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
    e = route_decision_event(
        "req1", "scnet_ds_flash", "reputation_top", candidates=["scnet_ds_flash", "github_gpt4o", "cf_qwen_coder"] * 2
    )
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
