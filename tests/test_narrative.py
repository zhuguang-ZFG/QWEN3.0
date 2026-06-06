from context_pipeline.narrative import (
    inject_handoff_context,
    reframe_for_handoff,
    should_reframe,
)


def test_reframe_marks_assistant_messages():
    messages = [
        {"role": "user", "content": "fix the bug"},
        {"role": "assistant", "content": "I'll fix it by changing line 42"},
        {"role": "user", "content": "that didn't work"},
    ]
    reframed = reframe_for_handoff(messages, "groq_llama70b", "scnet_qwen72b")
    assert reframed[1]["role"] == "user"
    assert "前一个助手" in reframed[1]["content"]
    assert "line 42" in reframed[1]["content"]


def test_reframe_preserves_user_messages():
    messages = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
    ]
    reframed = reframe_for_handoff(messages, "a", "b")
    assert reframed[0]["role"] == "user"
    assert reframed[0]["content"] == "hello"


def test_reframe_empty_from_backend_returns_unchanged():
    messages = [{"role": "user", "content": "test"}]
    result = reframe_for_handoff(messages, "", "b")
    assert result == messages


def test_should_reframe_true_on_error():
    assert should_reframe(1, "groq", "scnet") is True


def test_should_reframe_false_same_backend():
    assert should_reframe(1, "groq", "groq") is False


def test_should_reframe_false_no_error():
    assert should_reframe(0, "groq", "scnet") is False


def test_inject_handoff_context_adds_transition():
    messages = [
        {"role": "user", "content": "fix bug"},
        {"role": "assistant", "content": "trying..."},
    ]
    result = inject_handoff_context(messages, "groq", "scnet", "timeout")
    last = result[-1]
    assert "groq" in last["content"]
    assert "timeout" in last["content"]
    assert "重新回答" in last["content"]
