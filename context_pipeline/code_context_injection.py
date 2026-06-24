# DEPRECATED v3.0 — coding capability retired
"""Direct code context injection for coding scenarios (DEPRECATED).

Enhanced with semantic retrieval: finds relevant files even when not
explicitly mentioned in the query, using keyword scoring + graph expansion.

v3.0: coding capability retired. Main functions are disabled and return
safe default values to keep imports working.
"""

from __future__ import annotations

import logging
from pathlib import Path

_log = logging.getLogger(__name__)

_MAX_CONTEXT_CHARS = 4000
_MAX_FILES = 8


def extract_file_mentions(
    query: str,
    messages: list[dict] | None = None,
) -> tuple[list[str], list[str]]:
    """Extract file paths and code identifiers from query and recent messages. (DEPRECATED)"""
    return [], []


def scan_and_build_context(
    query: str,
    messages: list[dict] | None = None,
    max_chars: int = _MAX_CONTEXT_CHARS,
) -> str:
    """Build code context string for a coding query. (DEPRECATED)"""
    return ""


def _phase_semantic_retrieval(
    query: str,
    messages: list[dict] | None,
    parts: list[str],
    total: int,
    scanned: set[str],
    max_chars: int,
) -> tuple[list[str], int, set[str]]:
    """Phase 2: Semantic retrieval for implicit relevant files. (DEPRECATED)"""
    return parts, total, scanned


def _resolve_file(fname: str) -> Path | None:
    return None


def _scan_single_file(path: Path) -> str:
    return ""


def _find_identifier_files(identifier: str) -> list[Path]:
    return []
