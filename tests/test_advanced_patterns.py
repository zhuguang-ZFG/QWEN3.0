from context_pipeline.skill_store import SkillStore
from context_pipeline.evolution import (
    EvolutionStrategy,
    auto_select_strategy,
    get_strategy_config,
    apply_strategy_to_backends,
)


# === Phase 17: Skill Crystallization ===

def test_skill_crystallize_and_recall():
    store = SkillStore()
    messages = [{"role": "user", "content": "fix the routing bug in server.py"}]
    skill = store.crystallize(messages, "coding", "scnet_qwen72b", 5, 800)
    assert skill.backend == "scnet_qwen72b"
    assert skill.use_count == 1

    recalled = store.recall(messages, "coding")
    assert recalled is not None
    assert recalled.backend == "scnet_qwen72b"
    assert recalled.use_count == 2


def test_skill_recall_miss():
    store = SkillStore()
    messages = [{"role": "user", "content": "completely new request"}]
    assert store.recall(messages, "coding") is None


def test_skill_expiry():
    store = SkillStore()
    messages = [{"role": "user", "content": "test expiry"}]
    skill = store.crystallize(messages, "chat", "groq", 2, 200)
    # Phase 28: EMA decay — weight below 0.1 means expired
    skill.weight = 0.05
    assert skill.is_expired is True
    assert store.recall(messages, "chat") is None


def test_skill_store_eviction():
    store = SkillStore(max_skills=3)
    for i in range(5):
        store.crystallize(
            [{"role": "user", "content": f"request {i}"}],
            "coding", f"backend_{i}", 3, 500,
        )
    assert store.skill_count <= 3


# === Phase 18: GEP Evolution Strategies ===

def test_auto_select_repair_on_high_errors():
    strategy = auto_select_strategy(0.6, 0.3, 10)
    assert strategy == EvolutionStrategy.REPAIR


def test_auto_select_repair_on_few_backends():
    strategy = auto_select_strategy(0.1, 0.1, 2)
    assert strategy == EvolutionStrategy.REPAIR


def test_auto_select_harden_on_moderate_errors():
    strategy = auto_select_strategy(0.25, 0.1, 10)
    assert strategy == EvolutionStrategy.HARDEN


def test_auto_select_innovate_on_healthy():
    strategy = auto_select_strategy(0.02, 0.05, 20)
    assert strategy == EvolutionStrategy.INNOVATE


def test_auto_select_balanced_default():
    strategy = auto_select_strategy(0.1, 0.15, 10)
    assert strategy == EvolutionStrategy.BALANCED


def test_apply_strategy_prefers_proven_in_harden():
    backends = ["new1", "proven1", "new2", "proven2"]
    result = apply_strategy_to_backends(
        backends, EvolutionStrategy.HARDEN, proven_backends=["proven1", "proven2"]
    )
    assert result[0] == "proven1"
    assert result[1] == "proven2"


def test_strategy_config_properties():
    config = get_strategy_config(EvolutionStrategy.REPAIR)
    assert config.prefer_proven is True
    assert config.allow_weak_backends is False
    assert config.max_ensemble_size == 1
