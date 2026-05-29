"""Bridge M3 retrieval evaluation metrics to local retrieval indexes."""

from __future__ import annotations

from context_pipeline.retrieval_eval import (
    EvalSummary,
    RetrievalQuery,
    evaluate_queries,
    format_summary,
)
from local_retrieval.index import LocalRetrievalIndex


def evaluate_index(
    index: LocalRetrievalIndex,
    queries: list[RetrievalQuery],
    top_k: int = 5,
) -> EvalSummary:
    """Run eval queries against a local retrieval index."""
    retrieved: list[list[str]] = []
    for query in queries:
        hits = index.search(query.query, top_k=top_k)
        retrieved.append([hit.chunk_id for hit in hits])

    return evaluate_queries(queries, retrieved, k=top_k)


def format_eval_report(result: EvalSummary) -> str:
    """Format evaluation results as a readable report."""
    return format_summary(result)


def make_eval_query(
    query_text: str,
    expected_paths: list[str],
    description: str = "",
) -> RetrievalQuery:
    return RetrievalQuery(
        query=query_text,
        expected_paths=expected_paths,
        description=description,
    )
