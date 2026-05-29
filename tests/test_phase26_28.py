import os
import tempfile
import time

os.environ["LIMA_WEIGHTS_PATH"] = tempfile.mktemp(suffix=".json")

from context_pipeline.routing_weights import RoutingWeights
from context_pipeline.concurrency_pool import ConcurrencyPool
from context_pipeline.skill_store import SkillStore, RoutingSkill


# === Phase 26: GRPO Advantage Estimation ===

def test_grpo_success_when_baseline_low():
    """When baseline is low, success gives bigger boost."""
    rw = RoutingWeights()
    rw.record_failure("other", "coding")
    rw.record_failure("other", "coding")
    rw.record_success("good", "coding")
    assert rw.get_weight("good", "coding") > 1.0


def test_grpo_success_when_baseline_high():
    """When baseline is high, success gives smaller boost."""
    rw = RoutingWeights()
    for _ in range(5):
        rw.record_success("a", "chat")
        rw.record_success("b", "chat")
    w_before = rw.get_weight("a", "chat")
    rw.record_success("a", "chat")
    w_after = rw.get_weight("a", "chat")
    delta = w_after - w_before
    assert delta < 0.1


def test_grpo_failure_penalty_proportional():
    """Failure penalty is proportional to how much worse than baseline."""
    rw = RoutingWeights()
    rw.record_success("good", "coding")
    rw.record_success("good", "coding")
    rw.record_failure("bad", "coding")
    assert rw.get_weight("bad", "coding") < 1.0


def test_grpo_clipped_delta():
    """Delta is clipped to [-0.15, +0.15]."""
    import tempfile as _tf
    os.environ["LIMA_WEIGHTS_PATH"] = _tf.mktemp(suffix=".json")
    from importlib import reload
    import context_pipeline.routing_weights as _rw_mod
    reload(_rw_mod)
    rw = _rw_mod.RoutingWeights()
    rw.record_success("x", "coding")
    w = rw.get_weight("x", "coding")
    # Fresh instance: baseline=0.5, advantage=0.5, delta=0.04
    assert 1.0 < w <= 1.15


# === Phase 27: Concurrency Pool ===

def test_pool_acquire_and_release():
    pool = ConcurrencyPool(["key1", "key2"], max_concurrent=2)
    k = pool.acquire()
    assert k in ("key1", "key2")
    pool.release(k)


def test_pool_respects_concurrency_limit():
    pool = ConcurrencyPool(["key1"], max_concurrent=2)
    pool.acquire()
    pool.acquire()
    third = pool.acquire()
    assert third is None


def test_pool_release_frees_slot():
    pool = ConcurrencyPool(["key1"], max_concurrent=1)
    k = pool.acquire()
    assert pool.acquire() is None
    pool.release(k)
    assert pool.acquire() is not None


def test_pool_rate_limit_cooldown():
    pool = ConcurrencyPool(["key1", "key2"], max_concurrent=3)
    pool.mark_rate_limited("key1", cooldown_sec=60)
    k = pool.acquire()
    assert k == "key2"


def test_pool_rotate_on_failure():
    pool = ConcurrencyPool(["key1", "key2", "key3"], max_concurrent=3)
    next_key = pool.rotate_on_failure("key1")
    assert next_key in ("key2", "key3")


def test_pool_stats():
    pool = ConcurrencyPool(["a", "b", "c"], max_concurrent=2)
    pool.acquire()
    pool.acquire()
    stats = pool.stats()
    assert stats["total_keys"] == 3
    assert stats["in_flight"] == 2


# === Phase 28: Cognee EMA Decay ===

def test_skill_ema_success_grows_weight():
    store = SkillStore()
    messages = [{"role": "user", "content": "fix routing bug"}]
    skill = store.crystallize(messages, "coding", "scnet", 5, 800)
    initial_weight = skill.weight
    store.recall(messages, "coding")
    # on_success is deferred until confirm_success
    store.confirm_success()
    assert skill.weight > initial_weight


def test_skill_ema_failure_decays_weight():
    skill = RoutingSkill(
        skill_key="test", backend="x", scenario="coding",
        complexity_score=3, latency_ms=500,
        created_at=time.time(), last_used=time.time(),
        weight=1.0,
    )
    skill.on_failure()
    skill.on_failure()
    skill.on_failure()
    assert skill.weight < 0.75


def test_skill_ema_expired_when_weight_low():
    skill = RoutingSkill(
        skill_key="test", backend="x", scenario="coding",
        complexity_score=3, latency_ms=500,
        created_at=time.time(), last_used=time.time(),
        weight=0.05,
    )
    assert skill.is_expired is True


def test_skill_ema_weight_capped():
    skill = RoutingSkill(
        skill_key="test", backend="x", scenario="coding",
        complexity_score=3, latency_ms=500,
        created_at=time.time(), last_used=time.time(),
        weight=2.9,
    )
    skill.on_success()
    assert skill.weight <= 3.0
