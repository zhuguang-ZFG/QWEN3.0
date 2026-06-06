"""Tests for x-session-affinity header and tool repair integration (Round 4)."""

import pytest
from http_request_builder import _build_headers_with_affinity, _build_body


# ── x-session-affinity header ────────────────────────────────────────────────


class TestSessionAffinityHeader:
    def _cfg(self, fmt="openai", model="gpt-4o"):
        return {"fmt": fmt, "key": "test-key", "auth": "bearer", "model": model}

    def test_no_session_id(self):
        headers = _build_headers_with_affinity(self._cfg(), backend_name="openai_1")
        assert "x-session-affinity" not in headers

    def test_no_backend_name(self):
        headers = _build_headers_with_affinity(self._cfg(), session_id="sess123")
        assert "x-session-affinity" not in headers

    def test_adds_affinity_for_openai(self):
        headers = _build_headers_with_affinity(
            self._cfg(), backend_name="openai_1", session_id="sess123",
        )
        assert headers["x-session-affinity"] == "sess123"

    def test_adds_affinity_for_anthropic(self):
        cfg = self._cfg(fmt="anthropic", model="claude-3-opus")
        headers = _build_headers_with_affinity(
            cfg, backend_name="anthropic_1", session_id="s456",
        )
        assert headers["x-session-affinity"] == "s456"

    def test_standard_headers_preserved(self):
        headers = _build_headers_with_affinity(
            self._cfg(), backend_name="openai_1", session_id="s1",
        )
        assert headers["Content-Type"] == "application/json"
        assert headers["Authorization"] == "Bearer test-key"

    def test_opencode_zen_excluded(self):
        """opencode_zen provider should NOT get x-session-affinity."""
        headers = _build_headers_with_affinity(
            self._cfg(model="opencode-zen-model"),
            backend_name="opencode_zen_1",
            session_id="s1",
        )
        assert "x-session-affinity" not in headers


# ── Tool repair integration in _build_body ───────────────────────────────────


class TestToolRepairIntegration:
    def _cfg(self, model="gpt-4o"):
        return {"fmt": "openai", "key": "k", "auth": "bearer", "model": model}

    def test_invalid_tool_injected(self):
        tools = [
            {"type": "function", "function": {"name": "read_file", "parameters": {"type": "object"}}},
        ]
        body_bytes = _build_body(
            self._cfg(),
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=1000,
            tools=tools,
        )
        import json
        body = json.loads(body_bytes)
        tool_names = [t["function"]["name"] for t in body["tools"]]
        assert "invalid" in tool_names

    def test_invalid_tool_not_duplicated(self):
        tools = [
            {"type": "function", "function": {"name": "read_file", "parameters": {"type": "object"}}},
            {"type": "function", "function": {"name": "invalid", "parameters": {"type": "object"}}},
        ]
        body_bytes = _build_body(
            self._cfg(),
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=1000,
            tools=tools,
        )
        import json
        body = json.loads(body_bytes)
        invalid_count = sum(1 for t in body["tools"] if t["function"]["name"] == "invalid")
        assert invalid_count == 1
