from context_pipeline.cache import (
    compute_stable_prefix,
    compute_prefix_hash,
    build_cached_prompt,
    get_cache_metrics,
    CacheMetrics,
)


def test_compute_stable_prefix_deterministic():
    p1 = compute_stable_prefix("OpenCode", "coding")
    p2 = compute_stable_prefix("OpenCode", "coding")
    assert p1 == p2
    assert "编程助手" in p1
    assert "编码实现" in p1
    assert "质量门控" in p1


def test_compute_stable_prefix_different_for_different_scenarios():
    coding = compute_stable_prefix("OpenCode", "coding")
    chat = compute_stable_prefix("OpenCode", "chat")
    assert coding != chat
    assert "编程助手" in coding
    assert "联网能力" in chat


def test_compute_prefix_hash_consistent():
    prefix = compute_stable_prefix("OpenCode", "coding")
    h1 = compute_prefix_hash(prefix)
    h2 = compute_prefix_hash(prefix)
    assert h1 == h2
    assert len(h1) == 12


def test_build_cached_prompt_without_variable():
    prompt, prefix_hash = build_cached_prompt("OpenCode", "coding")
    assert "编程助手" in prompt
    assert "编码实现" in prompt
    assert "质量门控" in prompt
    assert len(prefix_hash) == 12


def test_build_cached_prompt_with_variable_content():
    prompt, _ = build_cached_prompt(
        "OpenCode", "coding",
        variable_content="[上下文]\nrouting_engine.py | select, classify"
    )
    assert "routing_engine.py" in prompt
    parts = prompt.split("\n\n")
    context_idx = next(i for i, p in enumerate(parts) if "routing_engine" in p)
    role_idx = next(i for i, p in enumerate(parts) if "编程助手" in p)
    assert role_idx < context_idx


def test_cache_metrics_tracks_requests():
    metrics = CacheMetrics()
    metrics.record("hash_a")
    metrics.record("hash_a")
    metrics.record("hash_b")

    assert metrics.total_requests == 3
    assert metrics.cache_eligible == 3
    assert metrics.unique_prefixes == 2
    assert metrics.hit_rate_estimate > 0.3


def test_same_ide_scenario_produces_same_hash():
    _, h1 = build_cached_prompt("OpenCode", "coding")
    _, h2 = build_cached_prompt("OpenCode", "coding")
    assert h1 == h2


def test_different_scenario_produces_different_hash():
    _, h1 = build_cached_prompt("OpenCode", "coding")
    _, h2 = build_cached_prompt("OpenCode", "chat")
    assert h1 != h2
