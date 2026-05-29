"""Retrieval Evaluation - lightweight metrics for context retrieval quality.

Uses a deterministic fixture corpus with expected results.
No network, no external services, no hosted evaluators.

Metrics:
    - recall: fraction of expected files/chunks that were retrieved
    - precision_at_k: fraction of retrieved results at rank k that are expected
    - hit_rate: fraction of queries where at least one expected result was found
    - mrr: mean reciprocal rank of the first expected result
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RetrievalQuery:
    query: str
    expected_paths: list[str]  # expected file paths or entity names
    description: str = ""


@dataclass
class RetrievalEvalResult:
    query: str
    retrieved_paths: list[str]
    expected_paths: list[str]
    recall: float
    precision_at_k: float
    hit: bool
    reciprocal_rank: float
    k: int = 5


@dataclass
class EvalSummary:
    queries: int
    mean_recall: float
    mean_precision_at_k: float
    hit_rate: float
    mean_mrr: float
    results: list[RetrievalEvalResult] = field(default_factory=list)


def compute_recall(expected: list[str], retrieved: list[str]) -> float:
    if not expected:
        return 1.0
    found = sum(1 for e in expected if e in retrieved)
    return found / len(expected)


def compute_precision_at_k(expected: list[str], retrieved: list[str], k: int = 5) -> float:
    top_k = retrieved[:k]
    if not top_k:
        return 0.0
    found = sum(1 for r in top_k if r in expected)
    return found / len(top_k)


def compute_reciprocal_rank(expected: list[str], retrieved: list[str]) -> float:
    for i, r in enumerate(retrieved, start=1):
        if r in expected:
            return 1.0 / i
    return 0.0


def evaluate_single(query: RetrievalQuery, retrieved_paths: list[str], k: int = 5) -> RetrievalEvalResult:
    recall = compute_recall(query.expected_paths, retrieved_paths)
    precision = compute_precision_at_k(query.expected_paths, retrieved_paths, k)
    hit = recall > 0.0
    mrr = compute_reciprocal_rank(query.expected_paths, retrieved_paths)
    return RetrievalEvalResult(
        query=query.query,
        retrieved_paths=retrieved_paths,
        expected_paths=query.expected_paths,
        recall=recall,
        precision_at_k=precision,
        hit=hit,
        reciprocal_rank=mrr,
        k=k,
    )


def evaluate_queries(queries: list[RetrievalQuery], retrieved: list[list[str]], k: int = 5) -> EvalSummary:
    results = [
        evaluate_single(query, retrieved[i] if i < len(retrieved) else [], k)
        for i, query in enumerate(queries)
    ]
    n = len(results)
    return EvalSummary(
        queries=n,
        mean_recall=sum(r.recall for r in results) / n if n else 0.0,
        mean_precision_at_k=sum(r.precision_at_k for r in results) / n if n else 0.0,
        hit_rate=sum(1 for r in results if r.hit) / n if n else 0.0,
        mean_mrr=sum(r.reciprocal_rank for r in results) / n if n else 0.0,
        results=results,
    )


def format_summary(summary: EvalSummary) -> str:
    lines = [
        f"Queries: {summary.queries}",
        f"Recall@{summary.results[0].k if summary.results else 5}: {summary.mean_recall:.3f}",
        f"Precision@{summary.results[0].k if summary.results else 5}: {summary.mean_precision_at_k:.3f}",
        f"Hit Rate: {summary.hit_rate:.3f}",
        f"MRR: {summary.mean_mrr:.3f}",
    ]
    return "\n".join(lines)
