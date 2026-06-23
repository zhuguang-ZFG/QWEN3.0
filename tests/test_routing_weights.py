from context_pipeline.routing_weights import RoutingWeights


def test_initial_weight_is_one():
    rw = RoutingWeights()
    assert rw.get_weight("scnet_qwen72b", "coding") == 1.0


def test_record_success_increases_weight():
    rw = RoutingWeights()
    rw.record_success("scnet_qwen72b", "coding")
    rw.record_success("scnet_qwen72b", "coding")
    assert rw.get_weight("scnet_qwen72b", "coding") > 1.0


def test_record_failure_decreases_weight():
    rw = RoutingWeights()
    rw.record_failure("groq_llama70b", "coding")
    rw.record_failure("groq_llama70b", "coding")
    assert rw.get_weight("groq_llama70b", "coding") < 1.0


def test_weight_capped_at_bounds():
    rw = RoutingWeights()
    for _ in range(50):
        rw.record_success("x", "coding")
    assert rw.get_weight("x", "coding") <= 2.0

    for _ in range(100):
        rw.record_failure("y", "coding")
    assert rw.get_weight("y", "coding") >= 0.1


def test_rank_backends_by_weight():
    rw = RoutingWeights()
    rw.record_success("strong", "coding")
    rw.record_success("strong", "coding")
    rw.record_failure("weak", "coding")
    rw.record_failure("weak", "coding")

    ranked = rw.rank_backends(["weak", "strong", "neutral"], "coding")
    assert ranked[0] == "strong"
    assert ranked[-1] == "weak"


def test_rank_backends_with_empty_list():
    rw = RoutingWeights()
    assert rw.rank_backends([], "chat") == []


def test_rank_backends_all_unknown():
    rw = RoutingWeights()
    ranked = rw.rank_backends(["a", "b", "c"], "chat")
    assert len(ranked) == 3


def test_backend_weight_success_rate():
    from context_pipeline.routing_weights import BackendWeight

    bw = BackendWeight(backend="b", scenario="s")
    assert bw.success_rate == 0.5  # no data
    bw.successes = 3
    bw.failures = 1
    assert abs(bw.success_rate - 0.75) < 0.01


def test_backend_weight_zero_total():
    from context_pipeline.routing_weights import BackendWeight

    bw = BackendWeight(backend="b", scenario="s", successes=0, failures=0)
    assert bw.success_rate == 0.5


def test_different_scenarios_independent():
    rw = RoutingWeights()
    rw.record_success("b1", "coding")
    rw.record_failure("b1", "chat")
    coding_w = rw.get_weight("b1", "coding")
    chat_w = rw.get_weight("b1", "chat")
    assert coding_w != chat_w


def test_get_stats():
    rw = RoutingWeights()
    rw.record_success("stats_be", "chat")
    rw.record_success("stats_be", "chat")
    rw.record_failure("stats_be", "chat")
    stats = rw.get_stats("stats_be", "chat")
    assert stats["successes"] == 2
    assert stats["failures"] == 1
    assert abs(stats["success_rate"] - 2 / 3) < 0.01


def test_get_stats_unknown_backend():
    rw = RoutingWeights()
    stats = rw.get_stats("nonexistent", "chat")
    assert stats["successes"] == 0
    assert stats["failures"] == 0
    assert stats["success_rate"] == 0.5  # default for no data
