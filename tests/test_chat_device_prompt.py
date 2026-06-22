"""Tests for device-intent system prompt merge on chat path."""

from __future__ import annotations

from prompt_engineering.device_intent_prompt import merge_device_intent_system_prompt


def test_merge_device_stop_uses_device_control_layers():
    prompt = merge_device_intent_system_prompt("急停", "")
    assert "设备控制助手" in prompt
    assert "急停" in prompt
    assert "质量门控" in prompt


def test_merge_non_device_intent_keeps_original_prompt():
    original = "You are a helpful assistant."
    assert merge_device_intent_system_prompt("解释一下 Python 装饰器", original) == original


def test_merge_device_draw_preserves_existing_context():
    original = "客户端自定义 system 片段"
    prompt = merge_device_intent_system_prompt("笔绘机画一只猫", original)
    assert "绘图助手" in prompt
    assert original in prompt
