"""Lightweight semantic quality evaluator -- pattern-based, no LLM call.

Scores responses on three dimensions:
- Relevance: does the response address query keywords?
- Completeness: is the response length appropriate for query complexity?
- Coherence: does the response have structure, not gibberish?

Returns score 0-100. Used alongside existing health_scoring.score_response_quality()
which handles refusal/truncation/repetition but NOT semantic relevance.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

# -- Query complexity estimation ----------------------------------------------

_SIMPLE_QUERY_MAX_WORDS = 5
_MEDIUM_QUERY_MAX_WORDS = 15

_COMPLEXITY_KEYWORDS = {
    "explain", "compare", "analyze", "design", "architect", "evaluate",
    "pros and cons", "trade-off", "benchmark", "optimize", "refactor",
    "\u89e3\u91ca", "\u6bd4\u8f83", "\u5206\u6790", "\u8bbe\u8ba1", "\u67b6\u6784", "\u8bc4\u4f30", "\u4f18\u5316", "\u91cd\u6784",
}


def _estimate_query_complexity(query: str) -> str:
    """Estimate query complexity as 'simple', 'medium', or 'complex'."""
    if not query:
        return "simple"
    words = query.split()
    has_complex_keyword = any(kw in query.lower() for kw in _COMPLEXITY_KEYWORDS)
    if has_complex_keyword or len(words) > _MEDIUM_QUERY_MAX_WORDS:
        return "complex"
    if len(words) > _SIMPLE_QUERY_MAX_WORDS:
        return "medium"
    return "simple"


# -- Expected response length ranges (chars) by complexity --------------------

_EXPECTED_LENGTH_RANGE = {
    "simple": (20, 2000),
    "medium": (50, 5000),
    "complex": (100, 15000),
}

# -- Relevance scoring --------------------------------------------------------

_STOP_WORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "shall",
    "should", "may", "might", "can", "could", "i", "you", "he", "she",
    "it", "we", "they", "me", "him", "her", "us", "them", "my", "your",
    "his", "its", "our", "their", "what", "which", "who", "whom", "this",
    "that", "these", "those", "am", "at", "by", "for", "with", "about",
    "to", "from", "in", "on", "of", "and", "or", "not", "no", "but",
    "if", "so", "as", "into", "how", "all", "each", "every", "both",
    "few", "more", "most", "other", "some", "such", "than", "too", "very",
    "just", "because", "any", "please", "want", "need", "like", "also",
    "\u7684", "\u4e86", "\u5728", "\u662f", "\u6211", "\u6709", "\u548c", "\u5c31", "\u4e0d", "\u4eba", "\u90fd",
    "\u4e00", "\u4e00\u4e2a", "\u4e0a", "\u4e5f", "\u5f88", "\u5230", "\u8bf4", "\u8981", "\u53bb", "\u4f60",
    "\u4f1a", "\u7740", "\u6ca1\u6709", "\u770b", "\u597d", "\u81ea\u5df1", "\u8fd9", "\u4ed6", "\u5979", "\u5417",
    "\u8bf7", "\u5e2e", "\u80fd", "\u53ef\u4ee5", "\u600e\u4e48", "\u4ec0\u4e48", "\u5982\u4f55", "\u4e3a\u4ec0\u4e48",
})


def _extract_keywords(text: str) -> set[str]:
    """Extract meaningful keywords from text (lowercase, no stop words)."""
    # Split on non-alphanumeric and non-CJK characters
    tokens = re.findall(r'[\w\u4e00-\u9fff]+', text.lower())
    return {t for t in tokens if t not in _STOP_WORDS and len(t) > 1}


def _score_relevance(query: str, response: str) -> float:
    """Score 0.0-1.0: how well does response address query keywords?

    Uses Jaccard-like overlap of query keywords found in response.
    A response that mentions most query terms scores high.
    """
    if not query or not response:
        return 0.5  # neutral when no query available

    query_kw = _extract_keywords(query)
    if not query_kw:
        return 0.7  # query was all stop words, assume neutral-good

    response_lower = response.lower()
    hits = sum(1 for kw in query_kw if kw in response_lower)
    coverage = hits / len(query_kw)

    # Scale: 0 keywords hit = 0.0, 50% hit = 0.6, 100% hit = 1.0
    return min(1.0, coverage * 1.2)


# -- Completeness scoring -----------------------------------------------------

def _score_completeness(query: str, response: str) -> float:
    """Score 0.0-1.0: is response length appropriate for query complexity?

    Too short = incomplete. Wildly too long = verbose padding.
    """
    if not response or not response.strip():
        return 0.0

    complexity = _estimate_query_complexity(query)
    lo, hi = _EXPECTED_LENGTH_RANGE[complexity]
    length = len(response.strip())

    # Too short: steep penalty
    if length < lo:
        return max(0.0, length / lo) if lo > 0 else 1.0

    # Within range: full score
    if length <= hi:
        return 1.0

    # Slightly over range: mild penalty (up to 3x expected max)
    overshoot = length / hi
    if overshoot <= 3.0:
        return max(0.5, 1.0 - (overshoot - 1.0) * 0.15)

    # Wildly over: significant penalty
    return max(0.2, 0.5 - (overshoot - 3.0) * 0.05)


# -- Coherence scoring --------------------------------------------------------

_SENTENCE_BOUNDARY = re.compile(r'[.!?。\uff01\uff1f\n]+')
_CODE_BLOCK_RE = re.compile(r'```[\s\S]*?```')
_LIST_ITEM_RE = re.compile(r'^[\s]*[-*+\d]+[.)]\s', re.MULTILINE)
_HEADING_RE = re.compile(r'^#{1,6}\s', re.MULTILINE)
_PARAGRAPH_BREAK_RE = re.compile(r'\n\s*\n')


def _score_coherence(response: str) -> float:
    """Score 0.0-1.0: does the response have structure and readability?

    Checks:
    - Has sentence/paragraph structure (not a wall of random chars)
    - Has some formatting (lists, code blocks, headings, paragraphs)
    - Character diversity (not repeated gibberish)
    """
    if not response or not response.strip():
        return 0.0

    text = response.strip()
    score = 1.0

    # -- Sentence structure --
    sentences = [s.strip() for s in _SENTENCE_BOUNDARY.split(text) if len(s.strip()) > 3]
    if len(sentences) == 0 and len(text) > 100:
        score -= 0.3  # long text with no sentence boundaries
    elif len(sentences) == 1 and len(text) > 200:
        score -= 0.15  # very long single sentence

    # -- Structural elements (bonus up to 0.0, penalty absent for long text) --
    has_code_blocks = bool(_CODE_BLOCK_RE.search(text))
    has_list_items = bool(_LIST_ITEM_RE.search(text))
    has_headings = bool(_HEADING_RE.search(text))
    has_paragraphs = bool(_PARAGRAPH_BREAK_RE.search(text))

    structural_elements = sum([has_code_blocks, has_list_items, has_headings, has_paragraphs])

    if len(text) > 300 and structural_elements == 0:
        score -= 0.2  # long text with no structure at all

    # -- Character diversity (gibberish detection) --
    alpha_chars = [c for c in text if c.isalpha()]
    if len(alpha_chars) > 20:
        unique_ratio = len(set(alpha_chars)) / len(alpha_chars)
        if unique_ratio < 0.05:
            score -= 0.4  # extremely low diversity = gibberish/repetition
        elif unique_ratio < 0.1:
            score -= 0.2

    # -- Unicode replacement chars (garbled encoding) --
    replacement_count = text.count('\ufffd')
    if replacement_count > 3:
        score -= min(0.3, replacement_count * 0.05)

    return max(0.0, min(1.0, score))


# -- Public API ---------------------------------------------------------------

@dataclass
class SemanticScore:
    """Breakdown of semantic quality evaluation."""
    total: float        # 0-100 composite score
    relevance: float    # 0.0-1.0
    completeness: float # 0.0-1.0
    coherence: float    # 0.0-1.0


# Dimension weights for composite score
_WEIGHT_RELEVANCE = 0.45
_WEIGHT_COMPLETENESS = 0.25
_WEIGHT_COHERENCE = 0.30


def evaluate_response(query: str, response: str) -> SemanticScore:
    """Evaluate response quality on relevance, completeness, and coherence.

    This is a PATTERN-BASED evaluator (no LLM call). It uses keyword overlap,
    length heuristics, and structural analysis.

    Args:
        query: The user's original query/question.
        response: The backend's response text.

    Returns:
        SemanticScore with total (0-100) and per-dimension scores (0.0-1.0).
    """
    relevance = _score_relevance(query, response)
    completeness = _score_completeness(query, response)
    coherence = _score_coherence(response)

    total = (
        relevance * _WEIGHT_RELEVANCE
        + completeness * _WEIGHT_COMPLETENESS
        + coherence * _WEIGHT_COHERENCE
    ) * 100.0

    return SemanticScore(
        total=round(total, 1),
        relevance=round(relevance, 3),
        completeness=round(completeness, 3),
        coherence=round(coherence, 3),
    )
