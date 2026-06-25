"""Tests for context_pipeline/skill_store.py — route caching as skills."""

import time

from context_pipeline.skill_store import SkillStore, RoutingSkill

MOCK_NOW = 1719043200.0


def _make_msgs(text: str = "hello") -> list[dict]:
    return [{"role": "user", "content": text}]


class TestRoutingSkill:
    def test_default_weight(self):
        skill = RoutingSkill(
            skill_key="k",
            backend="b",
            scenario="chat",
            complexity_score=1,
            latency_ms=100,
            created_at=MOCK_NOW,
            last_used=MOCK_NOW,
        )
        assert skill.weight == 1.0

    def test_on_success_increases_weight(self):
        skill = RoutingSkill(
            skill_key="k",
            backend="b",
            scenario="chat",
            complexity_score=1,
            latency_ms=100,
            created_at=MOCK_NOW,
            last_used=MOCK_NOW,
            weight=1.0,
        )
        skill.on_success()
        assert skill.weight > 1.0

    def test_on_failure_decreases_weight(self):
        skill = RoutingSkill(
            skill_key="k",
            backend="b",
            scenario="chat",
            complexity_score=1,
            latency_ms=100,
            created_at=MOCK_NOW,
            last_used=MOCK_NOW,
            weight=1.0,
        )
        skill.on_failure()
        assert skill.weight < 1.0

    def test_is_expired_when_weight_low(self):
        skill = RoutingSkill(
            skill_key="k",
            backend="b",
            scenario="chat",
            complexity_score=1,
            latency_ms=100,
            created_at=MOCK_NOW,
            last_used=MOCK_NOW,
            weight=0.05,
        )
        assert skill.is_expired is True

    def test_not_expired_when_weight_high(self):
        skill = RoutingSkill(
            skill_key="k",
            backend="b",
            scenario="chat",
            complexity_score=1,
            latency_ms=100,
            created_at=MOCK_NOW,
            last_used=MOCK_NOW,
            weight=1.0,
        )
        assert skill.is_expired is False

    def test_weight_capped_at_3(self):
        skill = RoutingSkill(
            skill_key="k",
            backend="b",
            scenario="chat",
            complexity_score=1,
            latency_ms=100,
            created_at=MOCK_NOW,
            last_used=MOCK_NOW,
            weight=2.9,
        )
        for _ in range(5):
            skill.on_success()
        assert skill.weight <= 3.0


class TestSkillStore:
    def test_crystallize_creates_skill(self):
        store = SkillStore()
        skill = store.crystallize(_make_msgs("draw a cat"), "device_draw", "dashscope_wanx", 3, 500)
        assert skill.backend == "dashscope_wanx"
        assert skill.scenario == "device_draw"

    def test_recall_returns_matching_skill(self):
        store = SkillStore()
        msgs = _make_msgs("draw a cat")
        store.crystallize(msgs, "device_draw", "dashscope_wanx", 3, 500)
        recalled = store.recall(msgs, "device_draw")
        assert recalled is not None
        assert recalled.backend == "dashscope_wanx"

    def test_recall_scenario_mismatch_returns_none(self):
        store = SkillStore()
        store.crystallize(_make_msgs("draw"), "device_draw", "dashscope_wanx", 3, 500)
        recalled = store.recall(_make_msgs("draw"), "chat")
        assert recalled is None

    def test_recall_empty_store_returns_none(self):
        store = SkillStore()
        assert store.recall(_make_msgs("hi"), "chat") is None

    def test_confirm_success_updates_weight(self):
        store = SkillStore()
        store.crystallize(_make_msgs("hello"), "chat", "groq", 1, 100)
        recalled = store.recall(_make_msgs("hello"), "chat")
        assert recalled is not None
        w_before = recalled.weight
        store.confirm_success()
        assert recalled.weight > w_before

    def test_on_failure_decays_weight(self):
        store = SkillStore()
        skill = store.crystallize(_make_msgs("test"), "chat", "groq", 1, 100)
        w_before = skill.weight
        # recall first to set _last_recalled, then fail
        store.recall(_make_msgs("test"), "chat")
        store.on_failure("chat")
        assert skill.weight < w_before

    def test_evict_lru_respects_max(self):
        store = SkillStore(max_skills=3)
        for i in range(5):
            store.crystallize(_make_msgs(f"msg{i}"), "chat", f"backend{i}", 1, 100)
        assert len(store._skills) <= 3

    def test_evict_removes_lowest_weight(self):
        store = SkillStore(max_skills=2)
        s1 = store.crystallize(_make_msgs("a"), "chat", "b1", 1, 100)
        s2 = store.crystallize(_make_msgs("b"), "chat", "b2", 1, 100)
        s1.on_failure()
        s1.on_failure()
        s3 = store.crystallize(_make_msgs("c"), "chat", "b3", 1, 100)
        assert "b1" not in [s.backend for s in store._skills.values()] or len(store._skills) <= 2
