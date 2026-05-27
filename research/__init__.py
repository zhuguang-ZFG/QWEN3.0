"""Multi-source research orchestrator for LiMa.

Searches across web, code, and documentation sources in parallel,
deduplicates, ranks, and synthesizes results into a coherent answer.
"""

from __future__ import annotations

from research.orchestrator import ResearchQuery, ResearchResult, run_research

__all__ = ["ResearchQuery", "ResearchResult", "run_research"]
