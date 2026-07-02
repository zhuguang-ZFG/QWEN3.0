"""Tests for routing_engine_post.py �?notification bridge & injected IDs."""

from __future__ import annotations

import types
import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def _patch_feedback_bridge(monkeypatch):
    """Patch routing_loop.feedback_bridge.on_request_complete."""
    import routing_engine.post as mod
    import sys

    calls = []

    def _fake_on_complete(**kw):
        calls.append(kw)

    fake_fb = types.ModuleType("routing_loop.feedback_bridge")
    fake_fb.on_request_complete = _fake_on_complete
    fake_mod_rlb = types.ModuleType("routing_loop")
    sys.modules["routing_loop.feedback_bridge"] = fake_fb
    sys.modules["routing_loop"] = fake_mod_rlb

    # Also patch make_chat_id
    monkeypatch.setattr(mod, "make_chat_id", lambda: "test-chat-id")

    yield calls
    sys.modules.pop("routing_loop.feedback_bridge", None)
    sys.modules.pop("routing_loop", None)


# ---------------------------------------------------------------------------
# _notify_feedback_bridge exception path
# ---------------------------------------------------------------------------


class TestNotifyFeedbackBridge:
    def test_happy_path(self, _patch_feedback_bridge):
        import routing_engine.post as mod

        mod._notify_feedback_bridge("chat", [], "groq", True, 100, False)
        assert len(_patch_feedback_bridge) == 1
        assert _patch_feedback_bridge[0]["backend"] == "groq"

    def test_exception_does_not_raise(self, monkeypatch, caplog):
        import sys
        import routing_engine.post as mod

        sys.modules.pop("routing_loop.feedback_bridge", None)

        import builtins

        _real_import = builtins.__import__

        def _bad_import(name, *args, **kwargs):
            if name == "routing_loop.feedback_bridge":
                raise ImportError("no such module")
            return _real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _bad_import)

        with caplog.at_level("WARNING"):
            mod._notify_feedback_bridge("chat", [], "x", False, 0, False)

        assert "feedback_bridge error" in caplog.text


# ---------------------------------------------------------------------------
# get_injected_ids
# ---------------------------------------------------------------------------


class TestGetInjectedIds:
    def test_no_injection_same_length(self):
        import routing_engine.post as mod

        msgs = [{"role": "user", "content": "hi"}]
        assert mod.get_injected_ids(msgs, msgs) == []

    def test_no_injection_shorter_modified(self):
        import routing_engine.post as mod

        original = [{"role": "user", "content": "a"}, {"role": "user", "content": "b"}]
        modified = [{"role": "user", "content": "a"}]
        assert mod.get_injected_ids(original, modified) == []

    def test_skill_injection_detected(self):
        import routing_engine.post as mod

        original = [{"role": "user", "content": "hi"}]
        modified = [
            {"role": "system", "content": "Available skills: foo, bar"},
            {"role": "user", "content": "hi"},
        ]
        result = mod.get_injected_ids(original, modified)
        assert result == ["dir:foo", "dir:bar"]

    def test_skill_injection_strips_whitespace(self):
        import routing_engine.post as mod

        original = [{"role": "user", "content": "hi"}]
        modified = [
            {"role": "system", "content": "Available skills: alpha , beta,  gamma"},
            {"role": "user", "content": "hi"},
        ]
        result = mod.get_injected_ids(original, modified)
        assert result == ["dir:alpha", "dir:beta", "dir:gamma"]

    def test_extra_skills_fallback(self):
        import routing_engine.post as mod

        original = [{"role": "user", "content": "hi"}]
        modified = [
            {"role": "system", "content": "some system prompt"},
            {"role": "user", "content": "hi"},
        ]
        result = mod.get_injected_ids(original, modified)
        assert result == ["injected_1_skills"]

    def test_empty_extra_returns_empty(self):
        """If modified is longer but extra count would be <= 0 (edge)."""
        import routing_engine.post as mod

        # Both empty �?same length, no injection
        assert mod.get_injected_ids([], []) == []
