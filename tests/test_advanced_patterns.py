from context_pipeline.skill_store import SkillStore


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
