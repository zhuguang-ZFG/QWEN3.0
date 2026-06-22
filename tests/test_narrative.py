"""Tests for context_pipeline/narrative.py — backend handoff context."""

from context_pipeline.narrative import reframe_for_handoff, should_reframe, inject_handoff_context


class TestReframeForHandoff:
    def test_empty_messages(self):
        assert reframe_for_handoff([], "a", "b") == []

    def test_no_from_backend(self):
        msgs = [{"role": "user", "content": "hi"}]
        assert reframe_for_handoff(msgs, "", "b") == msgs

    def test_reframes_assistant_messages(self):
        msgs = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "world"},
        ]
        result = reframe_for_handoff(msgs, "a", "b")
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "user"  # reframed
        assert "前一个助手" in result[1]["content"]

    def test_preserves_empty_assistant(self):
        msgs = [{"role": "assistant", "content": ""}]
        result = reframe_for_handoff(msgs, "a", "b")
        assert result[0]["role"] == "assistant"  # not reframed (empty)


class TestShouldReframe:
    def test_true_with_errors(self):
        assert should_reframe(1, "a", "b") is True

    def test_false_when_zero_errors(self):
        assert should_reframe(0, "a", "b") is False

    def test_false_when_same_backend(self):
        assert should_reframe(1, "a", "a") is False

    def test_false_when_missing_backend(self):
        assert should_reframe(1, "", "b") is False


class TestInjectHandoffContext:
    def test_returns_messages(self):
        msgs = [{"role": "user", "content": "test"}]
        result = inject_handoff_context(msgs, "a", "b", error_reason="timeout")
        assert isinstance(result, list)
        assert len(result) > len(msgs)  # adds transition note

    def test_includes_transition_note(self):
        msgs = [{"role": "user", "content": "hello"}]
        result = inject_handoff_context(msgs, "old_backend", "new_backend")
        assert any("old_backend" in str(m) for m in result)
