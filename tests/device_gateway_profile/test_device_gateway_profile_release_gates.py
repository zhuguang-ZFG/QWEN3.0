"""Docs/release gate tests."""

from pathlib import Path
from unittest.mock import AsyncMock

from device_gateway.device_route_memory import reset_route_memory_for_tests
from device_gateway.profiles import reset_profiles_for_tests


def setup_function():
    reset_profiles_for_tests()
    reset_route_memory_for_tests()


def test_model_admission_report_exists():
    """Verify the model admission report exists and is valid."""
    report_path = Path("docs/model_admission/2026-06-12-device-drawing-writing.md")
    assert report_path.exists(), "Model admission report should exist"

    content = report_path.read_text(encoding="utf-8")
    assert "Intent Parser" in content
    assert "Image Generator" in content
    assert "Vectorizer" in content
    assert "准入决策" in content


def test_release_gate_checklist_exists():
    """Verify the release gate checklist exists and covers all required gates."""
    checklist_path = Path("docs/RELEASE_GATE_CHECKLIST.md")
    assert checklist_path.exists(), "Release gate checklist should exist"

    content = checklist_path.read_text(encoding="utf-8")
    assert "门 A：服务器健康" in content
    assert "门 B：设备协议验证" in content
    assert "门 C：任务生命周期验证" in content
    assert "门 D：路由策略验证" in content
    assert "门 E：安全验证" in content
    assert "门 F：可观测性验证" in content


def test_release_evidence_exists():
    """Verify release evidence for phases 1-5 exists."""
    evidence_path = Path("docs/release_evidence/2026-06-12-phase1-5-complete.md")
    assert evidence_path.exists(), "Release evidence should exist"

    content = evidence_path.read_text(encoding="utf-8")
    assert "门 A" in content
    assert "门 B" in content
    assert "测试结果汇总" in content
