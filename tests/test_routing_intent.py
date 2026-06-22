"""Tests for routing_intent.py — intent detection and classification."""

import pytest

from routing_intent import (
    analyze_intent,
    intent_to_prompt_scenario,
    _rule_classify,
    _signal_classify,
)


class TestRuleClassify:
    """Rule-based classification tests."""

    def test_device_home(self):
        result = _rule_classify("回家")
        assert result is not None
        assert result["intent"] == "device_home"

    def test_device_stop(self):
        result = _rule_classify("急停")
        assert result["intent"] == "device_stop"

    def test_device_draw(self):
        result = _rule_classify("笔绘机画")
        assert result["intent"] == "device_draw"

    def test_device_write(self):
        result = _rule_classify("写一行字")
        assert result["intent"] == "device_write"

    def test_trivial_greeting(self):
        result = _rule_classify("你好")
        assert result is not None
        assert result["intent"] in ("trivial",)

    def test_grbl_config(self):
        result = _rule_classify("$100=200")
        assert result is not None
        assert result["intent"] == "grbl_config"

    def test_cnc_trouble(self):
        result = _rule_classify("机器有异响，电机失步")
        assert result["intent"] == "cnc_trouble"

    def test_image_gen(self):
        result = _rule_classify("画一张图片")
        assert result["intent"] == "image_gen"

    def test_no_match(self):
        """Non-matching query returns None."""
        result = _rule_classify("zzzunknownquery12345")
        assert result is None


class TestSignalClassify:
    """Signal-based classification tests."""

    def test_code_generation(self):
        result = _signal_classify("用Python写一个排序算法")
        assert result is not None
        assert result["intent"] == "code_generation"

    def test_debugging(self):
        result = _signal_classify("程序报错了，TypeError: undefined is not a function")
        assert result is not None
        assert result["intent"] == "debugging"

    def test_hardware(self):
        result = _signal_classify("ESP32 GPIO 配置问题")
        assert result is not None
        assert result["intent"] == "hardware"

    def test_trivial(self):
        result = _signal_classify("你好")
        assert result is not None
        assert result["intent"] == "trivial"

    def test_device_draw(self):
        result = _signal_classify("画一只简笔猫")
        assert result is not None
        assert result["intent"] == "device_draw"


class TestAnalyzeIntent:
    """End-to-end analyze_intent tests."""

    def test_device_home(self):
        result = analyze_intent("回家")
        assert result["intent"] == "device_home"

    def test_device_stop(self):
        result = analyze_intent("急停")
        assert result["intent"] == "device_stop"

    def test_device_draw(self):
        result = analyze_intent("笔绘机画图")
        assert result["intent"] == "device_draw"

    def test_device_write(self):
        result = analyze_intent("写一行字")
        assert result["intent"] == "device_write"

    def test_coding(self):
        result = analyze_intent("写代码帮我实现一个快排")
        assert result["intent"] in ("code_generation",)

    def test_trivial(self):
        result = analyze_intent("你好呀")
        assert result["intent"] in ("trivial",)

    def test_gcode_help(self):
        result = analyze_intent("G0 G1什么意思")
        assert result["intent"] == "gcode_help"

    def test_image_gen(self):
        result = analyze_intent("生成一张图片")
        assert result["intent"] == "image_gen"

    def test_embedded_dev(self):
        result = analyze_intent("ESP32 WiFi 连接问题")
        assert result["intent"] == "embedded_dev"

    def test_english_fallback(self):
        result = analyze_intent("What is the weather today?")
        assert result is not None
        # Should not crash on non-Chinese/non-CNC English input


class TestIntentToPromptScenario:
    def test_device_draw(self):
        assert intent_to_prompt_scenario("device_draw") == "device_draw"

    def test_device_write(self):
        assert intent_to_prompt_scenario("device_write") == "device_write"

    def test_device_home(self):
        assert intent_to_prompt_scenario("device_home") == "device_control"

    def test_device_stop(self):
        assert intent_to_prompt_scenario("device_stop") == "device_control"

    def test_unknown(self):
        assert intent_to_prompt_scenario("unknown_intent") is None

    def test_none(self):
        assert intent_to_prompt_scenario(None) is None
