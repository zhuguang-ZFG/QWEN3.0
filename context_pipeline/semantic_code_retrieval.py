# DEPRECATED v3.0 — coding capability retired
"""Semantic code retrieval — find relevant code files using keyword scoring (DEPRECATED).

Pure Python, zero external dependencies. Improves on regex-only extraction
by scoring files against query tokens with TF-IDF-like weighting.

v3.0: coding capability retired. Main functions are disabled and return
safe default values to keep imports working.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

_log = logging.getLogger(__name__)

_MAX_RESULTS = 10
_MIN_SCORE = 0.01


@dataclass
class CodeResult:
    file_path: str
    score: float
    snippet: str = ""
    symbols: list[str] | None = None
    related_files: list[str] | None = None


def retrieve_semantic(
    query: str,
    project_root: str = "",
    max_results: int = _MAX_RESULTS,
    messages: list[dict] | None = None,
) -> list[CodeResult]:
    """Find semantically relevant code files using keyword scoring. (DEPRECATED)"""
    return []


def assess_code_complexity(
    query: str,
    messages: list[dict] | None = None,
    project_root: str = "",
) -> float:
    """Assess how complex a coding request is. (DEPRECATED)"""
    return 0.0


def _extract_query_text(query: str, messages: list[dict] | None = None) -> str:
    return query


def _collect_identifier_terms(text: str) -> set[str]:
    return set()


_STOP_WORDS: set[str] = set()


def _filter_terms(terms: set[str]) -> list[str]:
    return []


def _tokenize_query(query: str, messages: list[dict] | None = None) -> list[str]:
    return []


def _build_file_index(root: Path) -> dict[str, dict]:
    return {}


def _score_file(terms: list[str], file_info: dict) -> float:
    return 0.0
