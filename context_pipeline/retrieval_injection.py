"""Single authoritative retrieval injection path for LiMa requests.

The entity extraction / production index / retrieval trace submodules were
removed in P1-9 because they had zero production fan-in.  The public API is
kept as a stable no-op so callers do not need to change.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RetrievalPayload:
    query_terms: list[str]
    candidates_searched: int
    reranked_results: list
    text: str


def run_retrieval(messages: list[dict]) -> RetrievalPayload | None:
    """Return no retrieved context.

    The cold retrieval chain was removed in P1-9; keeping this entry-point
    preserves the contract for ``routing_engine``.
    """
    return None


def build_retrieval_text(messages: list[dict]) -> str:
    """Return formatted retrieval text without mutating messages."""
    return ""


def inject_retrieval_context(messages: list[dict]) -> tuple[list[dict], str]:
    """Inject formatted retrieval context into messages and record trace evidence."""
    return messages, ""
