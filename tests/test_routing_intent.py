"""Tests for routing_intent helpers."""

import routing_intent


def test_detect_image_intent_chinese_draw():
    is_image, prompt = routing_intent.detect_image_intent("帮我画一只猫")
    assert is_image is True
    assert "猫" in prompt


def test_detect_image_intent_english_generate():
    is_image, prompt = routing_intent.detect_image_intent("generate an image of a sunset")
    assert is_image is True
    assert "sunset" in prompt.lower()


def test_detect_image_intent_non_image():
    is_image, prompt = routing_intent.detect_image_intent("explain quicksort in python")
    assert is_image is False
    assert prompt == ""


def test_detect_thinking_intent_chinese():
    assert routing_intent.detect_thinking_intent("仔细分析一下这个问题") is True


def test_detect_thinking_intent_english():
    assert routing_intent.detect_thinking_intent("think step by step") is True


def test_detect_thinking_intent_non_thinking():
    assert routing_intent.detect_thinking_intent("hello") is False
