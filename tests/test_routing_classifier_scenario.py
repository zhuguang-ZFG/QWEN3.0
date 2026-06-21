"""Tests for routing_classifier.classify_scenario parameter contract."""

from routing_classifier import classify_scenario


def test_classify_scenario_uses_messages_not_swapped_query():
    messages = [{"role": "user", "content": "写一个 Python 函数实现快排"}]
    assert classify_scenario(messages, query="sort algorithm in Python") == "coding"


def test_classify_scenario_chat_for_plain_greeting():
    messages = [{"role": "user", "content": "你好"}]
    assert classify_scenario(messages, query="你好") == "chat"
