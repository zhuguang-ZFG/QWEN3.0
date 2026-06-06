"""Tests for opencode_request_headers.py — request header parsing."""


from opencode_request_headers import (
    OpenCodeRequestContext,
    build_response_headers,
    extract_backend_from_session,
    is_opencode_client,
    parse_opencode_headers,
)


class TestParseOpenCodeHeaders:
    """parse_opencode_headers() tests."""

    def test_all_headers(self):
        headers = {
            "x-session-affinity": "sess-abc123",
            "x-opencode-session": "sess-abc123",
            "x-opencode-request": "req-xyz789",
            "x-opencode-client": "opencode/1.0.0",
            "x-parent-session-id": "parent-sess-001",
            "x-opencode-project": "proj-42",
        }
        ctx = parse_opencode_headers(headers)
        assert ctx.session_id == "sess-abc123"
        assert ctx.request_id == "req-xyz789"
        assert ctx.client_id == "opencode/1.0.0"
        assert ctx.parent_session_id == "parent-sess-001"
        assert ctx.project_id == "proj-42"
        assert ctx.is_compaction_request is True

    def test_minimal_headers(self):
        ctx = parse_opencode_headers({})
        assert ctx.session_id == ""
        assert ctx.request_id == ""
        assert ctx.has_session is False
        assert ctx.is_compaction_request is False

    def test_session_from_opencode_session_header(self):
        headers = {"x-opencode-session": "sess-direct"}
        ctx = parse_opencode_headers(headers)
        assert ctx.session_id == "sess-direct"

    def test_session_affinity_takes_priority(self):
        headers = {
            "x-session-affinity": "sess-affinity",
            "x-opencode-session": "sess-direct",
        }
        ctx = parse_opencode_headers(headers)
        assert ctx.session_id == "sess-affinity"

    def test_not_compaction_without_parent(self):
        headers = {"x-session-affinity": "sess-1"}
        ctx = parse_opencode_headers(headers)
        assert ctx.is_compaction_request is False

    def test_compaction_with_parent(self):
        headers = {"x-parent-session-id": "parent-1"}
        ctx = parse_opencode_headers(headers)
        assert ctx.is_compaction_request is True

    def test_affinity_key_session(self):
        ctx = parse_opencode_headers({"x-session-affinity": "sess-1"})
        assert ctx.affinity_key == "sess-1"

    def test_affinity_key_parent_fallback(self):
        ctx = parse_opencode_headers({"x-parent-session-id": "parent-1"})
        assert ctx.affinity_key == "parent-1"

    def test_affinity_key_empty(self):
        ctx = parse_opencode_headers({})
        assert ctx.affinity_key == ""

    def test_none_headers(self):
        ctx = parse_opencode_headers(None)
        assert ctx.session_id == ""

    def test_whitespace_trimming(self):
        headers = {"x-session-affinity": "  sess-trimmed  "}
        ctx = parse_opencode_headers(headers)
        assert ctx.session_id == "sess-trimmed"


class TestBuildResponseHeaders:
    """build_response_headers() tests."""

    def test_with_session(self):
        ctx = OpenCodeRequestContext(session_id="sess-1", request_id="req-1")
        headers = build_response_headers(ctx)
        assert headers["x-lima-session-id"] == "sess-1"
        assert headers["x-lima-request-id"] == "req-1"

    def test_empty_context(self):
        ctx = OpenCodeRequestContext()
        headers = build_response_headers(ctx)
        assert headers == {}


class TestExtractBackendFromSession:
    """extract_backend_from_session() tests."""

    def test_deterministic_selection(self):
        backends = ["backend_a", "backend_b", "backend_c"]
        result1 = extract_backend_from_session("sess-1", backends)
        result2 = extract_backend_from_session("sess-1", backends)
        assert result1 == result2  # Same session → same backend
        assert result1 in backends

    def test_different_sessions_may_differ(self):
        backends = [f"backend_{i}" for i in range(10)]
        results = set()
        for i in range(100):
            r = extract_backend_from_session(f"sess-{i}", backends)
            results.add(r)
        # With 100 sessions and 10 backends, should hit multiple
        assert len(results) > 1

    def test_empty_session(self):
        assert extract_backend_from_session("", ["a", "b"]) is None

    def test_empty_backends(self):
        assert extract_backend_from_session("sess-1", []) is None


class TestIsOpenCodeClient:
    """is_opencode_client() tests."""

    def test_direct_header(self):
        assert is_opencode_client({"x-opencode-client": "opencode/1.0"})

    def test_user_agent(self):
        assert is_opencode_client({"User-Agent": "OpenCode/2.0 IDE"})

    def test_not_opencode(self):
        assert not is_opencode_client({"User-Agent": "VSCode/1.0"})

    def test_empty(self):
        assert not is_opencode_client({})

    def test_case_insensitive_ua(self):
        assert is_opencode_client({"user-agent": "opencode/1.0"})
