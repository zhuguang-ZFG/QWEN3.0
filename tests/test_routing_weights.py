import os
import tempfile

os.environ["LIMA_WEIGHTS_PATH"] = tempfile.mktemp(suffix=".json")

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


def test_get_stats():
    rw = RoutingWeights()
    rw.record_success("b1", "chat")
    rw.record_success("b1", "chat")
    rw.record_failure("b1", "chat")
    stats = rw.get_stats("b1", "chat")
    assert stats["successes"] == 2
    assert stats["failures"] == 1
    assert abs(stats["success_rate"] - 2/3) < 0.01
