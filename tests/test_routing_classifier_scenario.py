"""Tests for routing_classifier.classify_scenario parameter contract."""

from routing_classifier import classify_scenario


def test_classify_scenario_coding_for_ide_request_type():
    messages = [{"role": "user", "content": "写一个 Python 函数实现快排"}]
    assert classify_scenario(messages, query="sort algorithm in Python", request_type="ide") == "coding"


def test_classify_scenario_coding_for_ide_source():
    messages = [{"role": "user", "content": "hello"}]
    assert classify_scenario(messages, query="hello", ide_source="vscode") == "coding"


def test_classify_scenario_chat_for_plain_greeting():
    messages = [{"role": "user", "content": "你好"}]
    assert classify_scenario(messages, query="你好") == "chat"


def test_classify_scenario_chat_for_code_signals():
    """v3.0: non-IDE code signals should no longer trigger coding scenario."""
    messages = [{"role": "user", "content": "写一个 Python 函数实现快排"}]
    assert classify_scenario(messages, query="sort algorithm in Python") == "chat"
