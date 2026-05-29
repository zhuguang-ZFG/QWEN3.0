"""Tests for router_classifier and router_intent (CQ-014 slice 6)."""

import router_classifier as clf
import router_intent as intent


def test_rule_classify_trivial_greeting():
    result = clf.rule_classify("你好")
    assert result is not None
    assert result["intent"] == "trivial"
    assert result["confidence"] >= 0.90


def test_rule_classify_grbl_config():
    result = clf.rule_classify("设置 $100 steps_per_mm")
    assert result is not None
    assert result["intent"] == "grbl_config"


def test_signal_classify_code_generation():
    result = clf.signal_classify("帮我用 python 实现一个排序算法")
    assert result is not None
    assert result["intent"] == "code_generation"
    assert result["needs_code"] is True


def test_analyze_thinking_takes_priority():
    result = clf.analyze("请仔细分析并证明根号2是无理数")
    assert result["intent"] == "thinking"
    assert result["source"] == "thinking_detect"


def test_analyze_code_block_detect():
    query = "```python\ndef foo():\n    pass\n```"
    result = clf.analyze(query, ide="cursor")
    assert result["intent"] == "code_generation"
    assert result["source"] in ("code_detect", "rules", "signal_v2", "ide_context")


def test_analyze_default_fallback():
    result = clf.analyze("xyz ambiguous request without strong signals")
    assert result["intent"] == "unknown"
    assert result["source"] == "default_fallback"


def test_detect_thinking_intent_patterns():
    assert intent.detect_thinking_intent("think step by step about this proof") is True
    assert intent.detect_thinking_intent("hello world") is False


def test_analyze_reexported_via_smart_router():
    import smart_router

    result = smart_router.analyze("你好")
    assert result["intent"] == "trivial"
