"""M4: Planner — map voice/text commands to structured TaskPlan objects."""

from __future__ import annotations

import pytest

from device_intelligence.planner import plan_from_text, PlannerError
from device_intelligence.schemas import TaskPlan


class TestPlannerControlCommands:
    """Control commands map to structured TaskPlan with correct capability."""

    @pytest.mark.parametrize(
        "text, expected_cap",
        [
            ("归零", "home"),
            ("回零", "home"),
            ("home", "home"),
            ("暂停", "pause"),
            ("pause", "pause"),
            ("继续", "resume"),
            ("resume", "resume"),
            ("停止", "stop"),
            ("stop", "stop"),
            ("设备信息", "get_device_info"),
            ("status", "get_device_info"),
        ],
    )
    def test_control_commands(self, text: str, expected_cap: str) -> None:
        plan = plan_from_text(text, device_id="dev-001")
        assert isinstance(plan, TaskPlan)
        assert plan.capability == expected_cap
        assert plan.device_id == "dev-001"
        assert plan.plan_id  # non-empty

    def test_empty_text_raises(self) -> None:
        with pytest.raises(PlannerError, match="empty"):
            plan_from_text("", device_id="dev-001")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(PlannerError, match="empty"):
            plan_from_text("   ", device_id="dev-001")


class TestPlannerWriteCommands:
    """Write text commands extract text param."""

    def test_chinese_write(self) -> None:
        plan = plan_from_text("写字你好世界", device_id="dev-002")
        assert plan.capability == "write_text"
        assert "你好世界" in plan.params.get("text", "")

    def test_english_write(self) -> None:
        plan = plan_from_text("write Hello World", device_id="dev-002")
        assert plan.capability == "write_text"
        assert "Hello World" in plan.params.get("text", "")


class TestPlannerDrawCommands:
    """Draw commands extract prompt param."""

    def test_chinese_draw(self) -> None:
        plan = plan_from_text("画个正方形", device_id="dev-003")
        assert plan.capability == "draw_generated"
        assert "正方形" in plan.params.get("prompt", "")

    def test_english_draw(self) -> None:
        plan = plan_from_text("draw a circle", device_id="dev-003")
        assert plan.capability == "draw_generated"
        assert "circle" in plan.params.get("prompt", "").lower()


class TestPlannerPlanId:
    """Each plan gets a unique plan_id."""

    def test_unique_ids(self) -> None:
        p1 = plan_from_text("归零", device_id="dev-001")
        p2 = plan_from_text("归零", device_id="dev-001")
        assert p1.plan_id != p2.plan_id

    def test_plan_has_source(self) -> None:
        plan = plan_from_text("归零", device_id="dev-001")
        assert plan.params.get("source") in ("voice", "planner")

    def test_plan_to_dict(self) -> None:
        plan = plan_from_text("归零", device_id="dev-001")
        d = plan.to_dict()
        assert d["capability"] == "home"
        assert d["device_id"] == "dev-001"
        assert "plan_id" in d
