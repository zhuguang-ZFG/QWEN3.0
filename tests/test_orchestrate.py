"""orchestrate.py — needs_orchestration and decompose fallback (Slice 4)."""

from __future__ import annotations

from unittest.mock import patch

import orchestrate


def test_needs_orchestration_simple_query():
    intent = {"intent": "grbl_config", "complexity": 0.3}
    assert not orchestrate.needs_orchestration("GRBL怎么设置", intent)


def test_needs_orchestration_cross_domain():
    intent = {"intent": "unknown", "complexity": 0.9}
    query = "请分别从硬件电路设计和软件编程两个角度，分析步进电机丢步问题的原因和解决方案"
    assert orchestrate.needs_orchestration(query, intent)


def test_decompose_fallback_to_single_task():
    with patch.object(orchestrate, "call_local", return_value="not json at all"):
        result = orchestrate.decompose("简单问题")
    assert len(result) == 1
    assert result[0]["task"] == "简单问题"
