"""Tests for routing_engine_post.py �?all branches."""

from __future__ import annotations

import types
import pytest


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _patch_integrations(monkeypatch):
    """Stub apply_post_route_integrations so we don't need real dependencies."""
    import routing_engine.post as mod

    calls = []
    monkeypatch.setattr(
        mod,
        "apply_post_route_integrations",
        lambda **kw: calls.append(kw),
    )
    return calls


@pytest.fixture()
def _patch_record_event(monkeypatch):
    """Patch routes.agent_events.record_event used by _record_routing_event."""

    calls = []

    def _fake_record(event_type, data):
        calls.append((event_type, data))

    # Patch the import inside _record_routing_event via sys.modules
    import sys

    fake_mod = types.ModuleType("routes.agent_events")
    fake_mod.record_event = _fake_record
    sys.modules["routes.agent_events"] = fake_mod
    yield calls
    sys.modules.pop("routes.agent_events", None)


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
# post_route tests
# ---------------------------------------------------------------------------


class TestPostRoute:
    """post_route() �?integrations, fallback detection, success flag."""

    def test_happy_path_no_fallback(self, _patch_integrations, _patch_record_event, _patch_feedback_bridge):
        import routing_engine.post as mod

        mod.post_route(
            answer="This is a long enough answer",
            final_backend="groq",
            backends=["groq", "openrouter"],
            messages_injected=[{"role": "user", "content": "hi"}],
            messages=[{"role": "user", "content": "hi"}],
            req_type="chat",
            scenario="chat",
            ms=120,
        )

        rec = _patch_record_event[-1]
        assert rec[0] == "routing_decision"
        assert rec[1]["success"] is True
        assert rec[1]["fallback_used"] is False

        fb = _patch_feedback_bridge[-1]
        assert fb["success"] is True
        assert fb["fallback_used"] is False
        assert fb["request_id"] == "test-chat-id"

    def test_fallback_path(self, _patch_integrations, _patch_record_event, _patch_feedback_bridge):
        import routing_engine.post as mod

        mod.post_route(
            answer="Another long answer",
            final_backend="openrouter",
            backends=["groq", "openrouter"],
            messages_injected=[],
            messages=[],
            req_type="chat",
            scenario="chat",
            ms=200,
        )

        rec = _patch_record_event[-1]
        assert rec[1]["fallback_used"] is True

    def test_exhausted_backend_not_fallback(self, _patch_integrations, _patch_record_event, _patch_feedback_bridge):
        import routing_engine.post as mod

        mod.post_route(
            answer="",
            final_backend="exhausted",
            backends=["groq"],
            messages_injected=[],
            messages=[],
            req_type="chat",
            scenario="chat",
            ms=50,
        )

        rec = _patch_record_event[-1]
        assert rec[1]["fallback_used"] is False  # exhausted is special-cased

    def test_success_false_short_answer(self, _patch_integrations, _patch_record_event, _patch_feedback_bridge):
        import routing_engine.post as mod

        mod.post_route(
            answer="hi",
            final_backend="groq",
            backends=["groq"],
            messages_injected=[],
            messages=[],
            req_type="chat",
            scenario="chat",
            ms=10,
        )

        rec = _patch_record_event[-1]
        assert rec[1]["success"] is False

    def test_success_false_none_answer(self, _patch_integrations, _patch_record_event, _patch_feedback_bridge):
        import routing_engine.post as mod

        mod.post_route(
            answer=None,
            final_backend="groq",
            backends=["groq"],
            messages_injected=[],
            messages=[],
            req_type="chat",
            scenario="chat",
            ms=10,
        )

        rec = _patch_record_event[-1]
        assert rec[1]["success"] is False

    def test_integrations_called_with_correct_args(
        self, _patch_integrations, _patch_record_event, _patch_feedback_bridge
    ):
        import routing_engine.post as mod

        msgs = [{"role": "user", "content": "test"}]
        mod.post_route(
            answer="ok answer here",
            final_backend="groq",
            backends=["groq", "nvidia"],
            messages_injected=msgs,
            messages=msgs,
            req_type="code",
            scenario="coding",
            ms=300,
        )

        kw = _patch_integrations[-1]
        assert kw["final_backend"] == "groq"
        assert kw["answer"] == "ok answer here"
        assert kw["backends"] == ["groq", "nvidia"]
        assert kw["req_type"] == "code"
        assert kw["scenario"] == "coding"
        assert kw["ms"] == 300

    def test_none_answer_coerced_to_empty(self, _patch_integrations, _patch_record_event, _patch_feedback_bridge):
        import routing_engine.post as mod

        mod.post_route(
            answer=None,
            final_backend="groq",
            backends=["groq"],
            messages_injected=[],
            messages=[],
            req_type="chat",
            scenario="chat",
            ms=5,
        )

        assert _patch_integrations[-1]["answer"] == ""


# ---------------------------------------------------------------------------
# _record_routing_event exception path
# ---------------------------------------------------------------------------


class TestRecordRoutingEvent:
    def test_happy_path(self, _patch_record_event):
        import routing_engine.post as mod

        mod._record_routing_event("groq", "chat", "chat", 100, True, False)
        assert len(_patch_record_event) == 1
        assert _patch_record_event[0][1]["backend"] == "groq"

    def test_exception_does_not_raise(self, monkeypatch, caplog):
        """When record_event import/invocation fails, we log at debug and continue."""
        import sys
        import routing_engine.post as mod

        # Remove the cached module so the lazy import inside _record_routing_event fires
        sys.modules.pop("routes.agent_events", None)

        # Make the import raise
        import builtins

        _real_import = builtins.__import__

        def _bad_import(name, *args, **kwargs):
            if name == "routes.agent_events":
                raise ImportError("no such module")
            return _real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _bad_import)

        with caplog.at_level("DEBUG"):
            mod._record_routing_event("x", "s", "r", 1, False, False)

        assert "routing_decision event record failed" in caplog.text


# ---------------------------------------------------------------------------
# _notify_feedback_bridge exception path
# ---------------------------------------------------------------------------

# NOTE: TestNotifyFeedbackBridge and TestGetInjectedIds moved to
# test_routing_engine_post_part2.py
