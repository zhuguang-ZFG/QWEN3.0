"""Tests for observability/events.py — LiMaEvent model and sanitization."""

from observability.events import LiMaEvent, _hash_session, _make_request_id


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
