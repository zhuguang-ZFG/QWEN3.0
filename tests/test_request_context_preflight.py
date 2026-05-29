from code_context.index_store import CodeSymbol, InMemoryCodeIndex
from request_context_preflight import enhance_messages, maybe_enhance_messages


def test_enhance_messages_adds_relevant_file_context_without_mutating_original():
    index = InMemoryCodeIndex()
    index.upsert_file(
        path="routing_engine.py",
        symbols=[CodeSymbol(name="select", kind="function", line=120)],
        imports=[],
        mtime=1.0,
    )
    messages = [{"role": "user", "content": "why did select backend fail?"}]

    enhanced = enhance_messages(messages, index=index, max_chars=500)

    assert messages == [{"role": "user", "content": "why did select backend fail?"}]
    assert enhanced[0]["role"] == "system"
    assert "routing_engine.py" in enhanced[0]["content"]
    assert "select:function:120" in enhanced[0]["content"]
    assert enhanced[1:] == messages


def test_enhance_messages_returns_original_when_no_context_matches():
    index = InMemoryCodeIndex()
    messages = [{"role": "user", "content": "hello"}]

    enhanced = enhance_messages(messages, index=index, max_chars=500)

    assert enhanced == messages


def test_preflight_disabled_keeps_messages_unchanged(monkeypatch):
    monkeypatch.delenv("LIMA_CONTEXT_PREFLIGHT", raising=False)
    messages = [{"role": "user", "content": "select backend"}]

    assert maybe_enhance_messages(messages, index=None) == messages


def test_preflight_enabled_delegates_to_unified_injector(monkeypatch):
    monkeypatch.setenv("LIMA_CONTEXT_PREFLIGHT", "1")
    messages = [{"role": "user", "content": "fix routing_engine.py"}]

    def fake_inject(msgs):
        return [{"role": "system", "content": "[代码上下文]"}] + list(msgs), "[代码上下文]"

    monkeypatch.setattr(
        "context_pipeline.retrieval_injection.inject_retrieval_context",
        fake_inject,
    )

    enhanced = maybe_enhance_messages(messages, index=None)

    assert enhanced[0]["content"] == "[代码上下文]"
    assert enhanced[1:] == messages
