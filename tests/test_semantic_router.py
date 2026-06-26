"""Tests for routing.semantic_router."""

from __future__ import annotations

import pytest

from routing.semantic_router import classify


@pytest.mark.parametrize(
    ("query", "expected_route"),
    [
        ("画一个圆", "image_gen"),
        ("帮我画只猫", "image_gen"),
        ("generate an image of a cat", "image_gen"),
        ("笔绘一个太阳", "device_draw"),
        ("让机器画棵树", "device_draw"),
        ("写一行你好", "device_write"),
        ("写首诗", "device_write"),
        ("回家", "device_control"),
        ("急停", "device_control"),
        ("设备在线吗", "device_control"),
        ("仔细想想这个问题", "thinking"),
        ("think step by step", "thinking"),
        ("用 python 写个排序", "code_generation"),
        ("生成代码示例", "code_generation"),
    ],
)
def test_high_confidence_queries(query, expected_route):
    result = classify(query, threshold=0.85)
    assert result is not None
    assert result[0] == expected_route
    assert result[2] >= 0.85


def test_low_confidence_returns_none():
    # Ambiguous query should not short-circuit intent analysis.
    assert classify("今天天气怎么样", threshold=0.85) is None


def test_empty_query_returns_none():
    assert classify("", threshold=0.85) is None
    assert classify("   ", threshold=0.85) is None


def test_threshold_tuning():
    # "画" alone is below 0.9 but above 0.7 with signal scoring.
    result_high = classify("画", threshold=0.9)
    assert result_high is None
    result_low = classify("画", threshold=0.7)
    assert result_low is not None


def test_intent_mapping():
    result = classify("写一行 hello")
    assert result is not None
    assert result[1] == "device_write"
