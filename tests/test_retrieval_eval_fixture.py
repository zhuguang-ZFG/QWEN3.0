"""Offline RAG eval fixture regression tests."""

import json
from pathlib import Path

import pytest

from context_pipeline.retrieval_eval_runner import (
    build_index_from_fixture,
    check_thresholds,
    collect_corpus_files,
    evaluate_fixture_index,
    format_fixture_report,
    load_fixture,
    resolve_corpus_files,
    run_fixture_eval,
)

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "retrieval_eval" / "lima_core.json"
ROUTING_FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "retrieval_eval" / "lima_routing.json"
)
ROUTING_PROD_FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "retrieval_eval" / "lima_routing_prod.json"
)


def test_load_lima_core_fixture():
    spec = load_fixture(FIXTURE_PATH)

    assert spec.name == "lima_core"
    assert spec.top_k == 5
    assert spec.match_by == "basename"
    assert len(spec.queries) == 4
    assert spec.corpus_root.is_dir()


def test_collect_corpus_files_sample_repo():
    spec = load_fixture(FIXTURE_PATH)
    files = collect_corpus_files(spec.corpus_root)

    assert any(path.endswith("module_a.py") for path in files)
    assert any(path.endswith("module_b.py") for path in files)


def test_lima_core_fixture_passes_gate():
    spec, summary, passed, failures = run_fixture_eval(FIXTURE_PATH)

    assert passed, failures
    assert summary.queries == len(spec.queries)
    assert summary.hit_rate >= spec.thresholds.min_hit_rate
    assert summary.mean_recall >= spec.thresholds.min_mean_recall
    assert summary.mean_mrr >= spec.thresholds.min_mean_mrr


def test_check_thresholds_detects_failures():
    from context_pipeline.retrieval_eval import EvalSummary

    summary = EvalSummary(
        queries=1,
        mean_recall=0.1,
        mean_precision_at_k=0.1,
        hit_rate=0.0,
        mean_mrr=0.0,
    )
    spec = load_fixture(FIXTURE_PATH)
    passed, failures = check_thresholds(summary, spec.thresholds)

    assert passed is False
    assert failures


def test_format_fixture_report_includes_gate_status():
    spec, summary, passed, failures = run_fixture_eval(FIXTURE_PATH)
    report = format_fixture_report(spec, summary, passed, failures)

    assert "lima_core" in report
    assert "Gate: PASS" in report


def test_evaluate_fixture_index_empty_corpus_fails_gate(tmp_path):
    empty_root = tmp_path / "empty"
    empty_root.mkdir()

    fixture = {
        "name": "empty",
        "corpus_root": str(empty_root),
        "top_k": 3,
        "match_by": "basename",
        "thresholds": {"min_hit_rate": 0.5, "min_mean_recall": 0.5, "min_mean_mrr": 0.25},
        "queries": [
            {"query": "anything", "expected_paths": ["missing.py"]},
        ],
    }
    path = tmp_path / "empty_fixture.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")

    spec = load_fixture(path)
    index = build_index_from_fixture(spec)
    summary = evaluate_fixture_index(index, spec)
    passed, _ = check_thresholds(summary, spec.thresholds)

    assert passed is False
    assert summary.hit_rate == 0.0


def test_lima_routing_fixture_dual_layer_passes_gate():
    spec, summary, passed, failures = run_fixture_eval(ROUTING_FIXTURE_PATH)

    assert spec.eval_mode == "dual_layer"
    assert len(spec.graph_relations) >= 3
    assert passed, failures
    assert summary.hit_rate >= spec.thresholds.min_hit_rate


def test_lima_routing_prod_fixture_uses_repo_files():
    spec = load_fixture(ROUTING_PROD_FIXTURE_PATH)

    assert spec.name == "lima_routing_prod"
    assert len(spec.corpus_files) >= 5
    paths = resolve_corpus_files(spec)
    assert any(path.endswith("routing_engine.py") for path in paths)
    assert any(path.endswith("http_caller.py") for path in paths)


def test_lima_routing_prod_fixture_dual_layer_passes_gate():
    spec, summary, passed, failures = run_fixture_eval(ROUTING_PROD_FIXTURE_PATH)

    assert spec.eval_mode == "dual_layer"
    assert passed, failures
    assert summary.hit_rate >= spec.thresholds.min_hit_rate


def test_evaluate_fixture_dual_layer_includes_graph_neighbors():
    from context_pipeline.retrieval_eval_runner import evaluate_fixture

    spec = load_fixture(ROUTING_FIXTURE_PATH)
    index = build_index_from_fixture(spec)
    summary = evaluate_fixture(index, spec)

    cross_query = next(r for r in summary.results if "route_request" in r.query)
    assert "health_tracker.py" in cross_query.retrieved_paths or cross_query.recall > 0
