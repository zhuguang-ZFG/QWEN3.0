"""Semantic code retrieval — find relevant code files using keyword scoring.

Pure Python, zero external dependencies. Improves on regex-only extraction
by scoring files against query tokens with TF-IDF-like weighting.
"""

from __future__ import annotations

import logging
import math
import os
import re
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
    """Find semantically relevant code files using keyword scoring.

    Uses a simple TF-IDF-like approach:
    1. Tokenize query into meaningful terms
    2. Score each Python file against query terms
    3. Boost files with matching symbols
    4. Return top results with snippets
    """
    root = _resolve_project_root(project_root)
    if not root.is_dir():
        return []

    terms = _tokenize_query(query, messages)
    if not terms:
        return []

    # Build file index (lazy, cached per call)
    file_index = _build_file_index(root)

    # Score each file
    scored: list[tuple[float, str, str]] = []
    for fpath, file_info in file_index.items():
        score = _score_file(terms, file_info)
        if score >= _MIN_SCORE:
            scored.append((score, fpath, file_info.get("snippet", "")))

    # Sort by score descending
    scored.sort(key=lambda x: -x[0])

    results = []
    for score, fpath, snippet in scored[:max_results]:
        file_info = file_index.get(fpath, {})
        results.append(CodeResult(
            file_path=fpath,
            score=round(score, 4),
            snippet=snippet[:500],
            symbols=file_info.get("symbols", [])[:10],
        ))

    return results


def assess_code_complexity(
    query: str,
    messages: list[dict] | None = None,
    project_root: str = "",
) -> float:
    """Assess how complex a coding request is (0.0 = simple, 1.0 = very complex).

    Based on: number of relevant files, depth of graph relationships,
    and query complexity indicators.
    """
    results = retrieve_semantic(query, project_root, max_results=5, messages=messages)
    if not results:
        return 0.0

    # Factor 1: number of relevant files
    file_count_score = min(len(results) / 5.0, 1.0)

    # Factor 2: query length and complexity indicators
    text = query.lower()
    complexity_indicators = [
        "refactor", "architecture", "design", "migrate", "optimize",
        "debug", "fix", "error", "broken", "race condition",
        "重构", "架构", "迁移", "优化", "调试",
    ]
    indicator_count = sum(1 for ind in complexity_indicators if ind in text)
    indicator_score = min(indicator_count / 3.0, 1.0)

    # Factor 3: cross-file references
    cross_ref_count = sum(
        1 for r in results
        if r.symbols and len(r.symbols) > 3
    )
    cross_ref_score = min(cross_ref_count / 3.0, 1.0)

    return min((file_count_score * 0.4 + indicator_score * 0.3 + cross_ref_score * 0.3), 1.0)


def _tokenize_query(query: str, messages: list[dict] | None = None) -> list[str]:
    """Extract meaningful search terms from query."""
    text = query
    if messages:
        for msg in messages[-2:]:
            if isinstance(msg, dict):
                text += " " + str(msg.get("content", ""))[:300]

    # Extract identifiers and keywords
    terms = set()

    # CamelCase and snake_case identifiers
    for match in re.finditer(r'\b([A-Z][a-zA-Z0-9]+)\b', text):
        terms.add(match.group(1).lower())
    for match in re.finditer(r'\b([a-z][a-z0-9_]{2,})\b', text):
        terms.add(match.group(1))

    # File names
    for match in re.finditer(r'([\w/\\.-]+\.(?:py|js|ts|go|rs|java))\b', text):
        terms.add(match.group(1).lower())

    # Stop words removal
    stop_words = {
        "the", "this", "that", "with", "from", "have", "been", "were",
        "does", "what", "when", "where", "which", "there", "their",
        "about", "would", "could", "should", "will", "just", "also",
        "some", "than", "them", "into", "over", "such", "your",
    }
    return [t for t in terms if t not in stop_words and len(t) > 1]


def _resolve_project_root(project_root: str = "") -> Path:
    root = Path(project_root or _detect_project_root())
    if root.is_dir() and (root / "routing_engine.py").exists():
        return root
    repo_root = Path(__file__).resolve().parent.parent
    if (repo_root / "routing_engine.py").exists():
        return repo_root
    return root


def _build_file_index(root: Path) -> dict[str, dict]:
    """Build a lightweight index of Python files in the project."""
    root = _resolve_project_root(str(root))
    index = {}
    py_files = list(root.rglob("*.py"))[:500]  # cap at 500 files

    for fpath in py_files:
        # Skip common unhelpful directories
        rel = str(fpath.relative_to(root))
        if any(skip in rel for skip in ("__pycache__", ".git", "venv", "node_modules", ".lima")):
            continue

        try:
            content = fpath.read_text(encoding="utf-8", errors="replace")[:8000]
        except (OSError, UnicodeDecodeError):
            continue

        # Extract symbols (simple regex, not tree-sitter for speed)
        symbols = []
        for match in re.finditer(r'^(?:class|def|async def)\s+(\w+)', content, re.MULTILINE):
            symbols.append(match.group(1))

        # Extract imports for graph-like relationships
        imports = []
        for match in re.finditer(r'^(?:from|import)\s+([\w.]+)', content, re.MULTILINE):
            imports.append(match.group(1))

        # Tokenize file content for scoring
        words = set(re.findall(r'\b[a-z_][a-z0-9_]{2,}\b', content.lower()))
        words.update(s.lower() for s in symbols)

        # Snippet: first meaningful lines
        lines = content.split("\n")
        snippet_lines = []
        for line in lines[:30]:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and not stripped.startswith('"""'):
                snippet_lines.append(stripped)
            if len(snippet_lines) >= 5:
                break

        index[rel] = {
            "path": str(fpath),
            "symbols": symbols,
            "imports": imports,
            "words": words,
            "snippet": "\n".join(snippet_lines),
            "size": len(content),
        }

    return index


def _score_file(terms: list[str], file_info: dict) -> float:
    """Score a file against query terms using TF-IDF-like weighting."""
    words = file_info.get("words", set())
    symbol_set = set(s.lower() for s in file_info.get("symbols", []))

    score = 0.0
    for term in terms:
        # Exact symbol match (highest weight)
        if term in symbol_set:
            score += 3.0
        # Word match in file content
        elif term in words:
            score += 1.0
        # Partial match (prefix)
        elif any(term.startswith(w) or w.startswith(term) for w in words if len(w) > 3):
            score += 0.3

    # Normalize by file size (prefer smaller, more focused files)
    size = file_info.get("size", 1000)
    size_factor = 1.0 / (1.0 + math.log1p(size / 5000))

    return score * size_factor


def _detect_project_root() -> str:
    env_root = os.environ.get("LIMA_PROJECT_ROOT", "")
    if env_root and os.path.isdir(env_root):
        return env_root
    cwd = os.getcwd()
    candidates = [cwd, "/opt/lima-router"]
    for p in candidates:
        if os.path.isdir(p) and os.path.exists(os.path.join(p, "routing_engine.py")):
            return p
    return cwd
