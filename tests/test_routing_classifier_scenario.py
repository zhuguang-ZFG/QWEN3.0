"""Tests for routing_classifier.classify_scenario parameter contract."""

from routing_classifier import classify_scenario


def test_classify_scenario_chat_for_ide_request_type():
    messages = [{"role": "user", "content": "写一个 Python 函数实现快排"}]
    assert classify_scenario(messages, query="sort algorithm in Python", request_type="ide") == "chat"


def test_classify_scenario_chat_for_ide_source():
    messages = [{"role": "user", "content": "hello"}]
    assert classify_scenario(messages, query="hello", ide_source="vscode") == "chat"


def test_classify_scenario_chat_for_plain_greeting():
    messages = [{"role": "user", "content": "你好"}]
    assert classify_scenario(messages, query="你好") == "chat"


def test_classify_scenario_chat_for_code_signals():
    """v3.0: non-IDE code signals should no longer trigger coding scenario."""
    messages = [{"role": "user", "content": "写一个 Python 函数实现快排"}]
    assert classify_scenario(messages, query="sort algorithm in Python") == "chat"


def test_routing_engine_classify_and_recall_skips_retired_logic(monkeypatch):
    """AUDIT-8-P9：classify_scenario 与 inject_retrieval_context 不应在热路径被调用。"""
    import routing_engine

    classify_calls = []
    retrieval_calls = []

    monkeypatch.setattr(
        routing_engine,
        "classify_scenario",
        lambda *args, **kwargs: classify_calls.append((args, kwargs)) or "chat",
    )
    monkeypatch.setattr(
        routing_engine,
        "inject_retrieval_context",
        lambda *args, **kwargs: retrieval_calls.append((args, kwargs)) or (args[0], ""),
    )

    req_type, scenario, recall_attempt, retrieval_text = routing_engine._classify_and_recall(
        query="hello",
        messages=[{"role": "user", "content": "hello"}],
        fmt="openai",
        ide_source="",
        system_prompt="",
        headers={},
    )

    assert scenario == "chat"
    assert retrieval_text == ""
    assert not classify_calls
    assert not retrieval_calls
