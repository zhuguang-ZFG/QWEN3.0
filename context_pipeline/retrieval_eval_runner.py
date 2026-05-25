"""Offline RAG eval runner: load fixture JSON, index corpus, score retrieval."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from context_pipeline.retrieval_eval import (
    EvalSummary,
    RetrievalQuery,
    evaluate_queries,
    format_summary,
)
from local_retrieval.index import InMemoryTokenIndex, LocalRetrievalIndex


@dataclass
class EvalThresholds:
    min_hit_rate: float = 0.5
    min_mean_recall: float = 0.5
    min_mean_mrr: float = 0.25


@dataclass
class GraphRelation:
    source: str
    target: str
    relation_type: str = "imports"


@dataclass
class FixtureSpec:
    name: str
    corpus_root: Path
    top_k: int
    match_by: str
    thresholds: EvalThresholds
    queries: list[RetrievalQuery] = field(default_factory=list)
    eval_mode: str = "index"
    graph_relations: list[GraphRelation] = field(default_factory=list)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _resolve_path(path_str: str, base: Path) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path.resolve()
    return (base / path).resolve()


def load_fixture(path: str | Path) -> FixtureSpec:
    """Load eval fixture JSON into a FixtureSpec."""
    fixture_path = Path(path).resolve()
    with open(fixture_path, encoding="utf-8") as handle:
        data = json.load(handle)

    thresholds_raw = data.get("thresholds", {})
    thresholds = EvalThresholds(
        min_hit_rate=float(thresholds_raw.get("min_hit_rate", 0.5)),
        min_mean_recall=float(thresholds_raw.get("min_mean_recall", 0.5)),
        min_mean_mrr=float(thresholds_raw.get("min_mean_mrr", 0.25)),
    )

    corpus_root = _resolve_path(data["corpus_root"], _repo_root())
    queries = [
        RetrievalQuery(
            query=item["query"],
            expected_paths=list(item.get("expected_paths", [])),
            description=item.get("description", ""),
        )
        for item in data.get("queries", [])
    ]
    graph_relations = [
        GraphRelation(
            source=rel["source"],
            target=rel["target"],
            relation_type=rel.get("relation_type", rel.get("type", "imports")),
        )
        for rel in data.get("graph_relations", [])
    ]

    return FixtureSpec(
        name=data.get("name", fixture_path.stem),
        corpus_root=corpus_root,
        top_k=int(data.get("top_k", 5)),
        match_by=data.get("match_by", "basename"),
        thresholds=thresholds,
        queries=queries,
        eval_mode=data.get("eval_mode", "index"),
        graph_relations=graph_relations,
    )


def collect_corpus_files(corpus_root: Path, extensions: tuple[str, ...] = (".py", ".md", ".txt")) -> list[str]:
    """Collect indexable files under corpus_root."""
    if not corpus_root.is_dir():
        return []

    files: list[str] = []
    for root, _dirs, names in os.walk(corpus_root):
        for name in names:
            if name.endswith(extensions):
                files.append(str(Path(root) / name))
    return sorted(files)


def build_index_from_fixture(spec: FixtureSpec, max_chars: int = 800) -> InMemoryTokenIndex:
    """Build a toy token index from fixture corpus_root."""
    index = InMemoryTokenIndex(index_id=f"fixture-{spec.name}", max_chars=max_chars)
    paths = collect_corpus_files(spec.corpus_root)
    index.add_documents(paths)
    return index


def _hit_to_match_path(hit, match_by: str) -> str:
    if match_by == "chunk_id":
        return hit.chunk_id
    return os.path.basename(hit.document_path)


def evaluate_fixture_index(
    index: LocalRetrievalIndex,
    spec: FixtureSpec,
) -> EvalSummary:
    retrieved: list[list[str]] = []
    for query in spec.queries:
        hits = index.search(query.query, top_k=spec.top_k)
        retrieved.append([_hit_to_match_path(hit, spec.match_by) for hit in hits])
    return evaluate_queries(spec.queries, retrieved, k=spec.top_k)


def build_graph_from_fixture(spec: FixtureSpec):
    from context_pipeline.graph_retrieval import CodeGraph

    graph = CodeGraph()
    for rel in spec.graph_relations:
        graph.add_relation(rel.source, rel.target, rel.relation_type)
    return graph


def evaluate_fixture_dual_layer(
    index: LocalRetrievalIndex,
    spec: FixtureSpec,
) -> EvalSummary:
    from context_pipeline.graph_retrieval import RetrievalResult, dual_layer_search

    graph = build_graph_from_fixture(spec)
    retrieved: list[list[str]] = []
    for query in spec.queries:
        hits = index.search(query.query, top_k=spec.top_k)
        vector_results = [
            RetrievalResult(
                path=_hit_to_match_path(hit, spec.match_by),
                score=max(hit.score, 0.1),
                source="vector",
            )
            for hit in hits
        ]
        seed_entities = [_hit_to_match_path(hit, spec.match_by) for hit in hits[:2]]
        if not seed_entities and vector_results:
            seed_entities = [vector_results[0].path]
        merged = dual_layer_search(
            seed_entities,
            vector_results,
            graph,
            max_results=spec.top_k,
        )
        retrieved.append([result.path for result in merged])
    return evaluate_queries(spec.queries, retrieved, k=spec.top_k)


def evaluate_fixture(
    index: LocalRetrievalIndex,
    spec: FixtureSpec,
) -> EvalSummary:
    if spec.eval_mode == "dual_layer" and spec.graph_relations:
        return evaluate_fixture_dual_layer(index, spec)
    return evaluate_fixture_index(index, spec)


def check_thresholds(summary: EvalSummary, thresholds: EvalThresholds) -> tuple[bool, list[str]]:
    """Return (passed, failure_messages)."""
    failures: list[str] = []
    if summary.hit_rate < thresholds.min_hit_rate:
        failures.append(
            f"hit_rate {summary.hit_rate:.3f} < {thresholds.min_hit_rate:.3f}"
        )
    if summary.mean_recall < thresholds.min_mean_recall:
        failures.append(
            f"mean_recall {summary.mean_recall:.3f} < {thresholds.min_mean_recall:.3f}"
        )
    if summary.mean_mrr < thresholds.min_mean_mrr:
        failures.append(
            f"mean_mrr {summary.mean_mrr:.3f} < {thresholds.min_mean_mrr:.3f}"
        )
    return (len(failures) == 0, failures)


def run_fixture_eval(path: str | Path) -> tuple[FixtureSpec, EvalSummary, bool, list[str]]:
    """Load fixture, build index, evaluate, and gate on thresholds."""
    spec = load_fixture(path)
    index = build_index_from_fixture(spec)
    summary = evaluate_fixture(index, spec)
    passed, failures = check_thresholds(summary, spec.thresholds)
    return spec, summary, passed, failures


def format_fixture_report(spec: FixtureSpec, summary: EvalSummary, passed: bool, failures: list[str]) -> str:
    """Human-readable report for CLI or test output."""
    lines = [
        f"Fixture: {spec.name}",
        f"Corpus: {spec.corpus_root}",
        f"Match by: {spec.match_by}",
        f"Eval mode: {spec.eval_mode}",
        format_summary(summary),
        f"Gate: {'PASS' if passed else 'FAIL'}",
    ]
    if failures:
        lines.extend(f"  - {msg}" for msg in failures)
    return "\n".join(lines)
