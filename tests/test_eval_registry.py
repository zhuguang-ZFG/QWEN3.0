import importlib

import eval_registry
from eval_registry import EvalEntry


def test_default_registry_path_stays_inside_repo_data(monkeypatch):
    monkeypatch.delenv("LIMA_EVAL_REGISTRY", raising=False)
    module = importlib.reload(eval_registry)

    assert module._EVAL_PATH.endswith("data\\eval_registry.jsonl") or module._EVAL_PATH.endswith(
        "data/eval_registry.jsonl"
    )
    assert "D:\\GIT\\data" in module._EVAL_PATH or "/GIT/data" in module._EVAL_PATH


def test_record_query_filter_summary_and_latest_limit(monkeypatch, tmp_path):
    registry_path = tmp_path / "eval_registry.jsonl"
    monkeypatch.setattr(eval_registry, "_EVAL_PATH", str(registry_path))

    eval_registry.record_eval(
        EvalEntry(
            model="old-model",
            backend="local",
            fixture="route-fixture",
            timestamp=1,
            score=0.7,
            passed=True,
            promoted_to="floor",
            cost_estimated_usd=0.1,
        )
    )
    eval_registry.record_eval(
        EvalEntry(
            model="new-model",
            backend="local",
            fixture="route-fixture",
            timestamp=2,
            score=0.9,
            passed=True,
            promoted_to="strong",
            cost_estimated_usd=0.2,
        )
    )
    eval_registry.record_eval(
        EvalEntry(
            model="failed-model",
            backend="remote",
            fixture="other",
            timestamp=3,
            score=0.2,
            passed=False,
            fail_reason="quality_floor",
        )
    )

    local_entries = eval_registry.query_evals(backend="local")
    assert [entry.model for entry in local_entries] == ["old-model", "new-model"]

    latest = eval_registry.latest_promoted(limit=1)
    assert [entry.model for entry in latest] == ["new-model"]

    stats = eval_registry.summary()
    assert stats["total_evals"] == 3
    assert stats["passed"] == 2
    assert stats["failed"] == 1
    assert stats["promoted"] == 2
    assert stats["total_cost_estimated_usd"] == 0.3
    assert stats["latest_eval_at"] == 3
