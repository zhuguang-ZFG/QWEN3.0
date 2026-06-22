"""Tests for routing_intent.analyze_intent (legacy router_classifier replacement)."""

import routing_intent as intent


def test_analyze_intent_trivial_greeting():
    result = intent.analyze_intent("你好")
    assert result is not None
    assert result["intent"] == "trivial"
    assert result["confidence"] >= 0.90


def test_analyze_intent_grbl_config():
    result = intent.analyze_intent("设置 $100 steps_per_mm")
    assert result is not None
    assert result["intent"] == "grbl_config"


def test_analyze_intent_code_generation():
    result = intent.analyze_intent("帮我用 python 实现一个排序算法")
    assert result is not None
    assert result["intent"] == "code_generation"
    assert result["needs_code"] is True


def test_analyze_intent_thinking_takes_priority():
    result = intent.analyze_intent("请仔细分析并证明根号2是无理数")
    assert result["intent"] == "thinking"
    assert result["source"] == "thinking_detect"


def test_analyze_intent_code_block_detect():
    query = "```python\ndef foo():\n    pass\n```"
    result = intent.analyze_intent(query, ide="cursor")
    assert result["intent"] == "code_generation"
    assert result["source"] in ("code_detect", "rules", "signal_v2", "ide_context")


def test_analyze_intent_default_fallback():
    result = intent.analyze_intent("xyz ambiguous request without strong signals")
    assert result["intent"] == "chat"
    assert result["source"] == "default_fallback"


def test_analyze_intent_device_home():
    result = intent.analyze_intent("帮我回家")
    assert result["intent"] == "device_home"
    assert result["confidence"] >= 0.90


def test_analyze_intent_device_stop():
    result = intent.analyze_intent("急停")
    assert result["intent"] == "device_stop"


def test_analyze_intent_device_write():
    result = intent.analyze_intent("写一行生日快乐")
    assert result["intent"] == "device_write"


def test_analyze_intent_device_status():
    result = intent.analyze_intent("设备在线吗")
    assert result["intent"] == "device_status"


def test_detect_thinking_intent_patterns():
    assert intent.detect_thinking_intent("think step by step about this proof") is True
    assert intent.detect_thinking_intent("hello world") is False
