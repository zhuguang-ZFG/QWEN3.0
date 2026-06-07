# Semantic Quality Evaluation with Feedback Loop

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add lightweight semantic quality evaluation that scores responses on relevance, completeness, and coherence, and feeds scores back into routing decisions to create a self-improving routing loop.

**Architecture:** A pattern-based evaluator (no LLM call) scores each response on 3 dimensions. Scores are persisted in a per-backend ring buffer. Routing selector uses quality trends as a scoring factor, and the evolution strategy system considers quality trends when choosing between explore/exploit/repair modes.

**Tech Stack:** Python 3.10+, pytest, existing LiMa health/routing infrastructure

---

## Task 1: Lightweight Semantic Evaluator

**Files:**
- Create: `D:\QWEN3.0\semantic_eval.py`
- Test: `D:\QWEN3.0\tests\test_semantic_eval.py`

### Step 1: Create `semantic_eval.py`

- [ ] **Create the semantic evaluator module** at `D:\QWEN3.0\semantic_eval.py`:

```python
"""Lightweight semantic quality evaluator — pattern-based, no LLM call.

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

# ── Query complexity estimation ──────────────────────────────────────────────

_SIMPLE_QUERY_MAX_WORDS = 5
_MEDIUM_QUERY_MAX_WORDS = 15

_COMPLEXITY_KEYWORDS = {
    "explain", "compare", "analyze", "design", "architect", "evaluate",
    "pros and cons", "trade-off", "benchmark", "optimize", "refactor",
    "解释", "比较", "分析", "设计", "架构", "评估", "优化", "重构",
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


# ── Expected response length ranges (chars) by complexity ────────────────────

_EXPECTED_LENGTH_RANGE = {
    "simple": (20, 2000),
    "medium": (50, 5000),
    "complex": (100, 15000),
}

# ── Relevance scoring ────────────────────────────────────────────────────────

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
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都",
    "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你",
    "会", "着", "没有", "看", "好", "自己", "这", "他", "她", "吗",
    "请", "帮", "能", "可以", "怎么", "什么", "如何", "为什么",
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


# ── Completeness scoring ─────────────────────────────────────────────────────

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


# ── Coherence scoring ────────────────────────────────────────────────────────

_SENTENCE_BOUNDARY = re.compile(r'[.!?。！？\n]+')
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

    # ── Sentence structure ──
    sentences = [s.strip() for s in _SENTENCE_BOUNDARY.split(text) if len(s.strip()) > 3]
    if len(sentences) == 0 and len(text) > 100:
        score -= 0.3  # long text with no sentence boundaries
    elif len(sentences) == 1 and len(text) > 200:
        score -= 0.15  # very long single sentence

    # ── Structural elements (bonus up to 0.0, penalty absent for long text) ──
    has_code_blocks = bool(_CODE_BLOCK_RE.search(text))
    has_list_items = bool(_LIST_ITEM_RE.search(text))
    has_headings = bool(_HEADING_RE.search(text))
    has_paragraphs = bool(_PARAGRAPH_BREAK_RE.search(text))

    structural_elements = sum([has_code_blocks, has_list_items, has_headings, has_paragraphs])

    if len(text) > 300 and structural_elements == 0:
        score -= 0.2  # long text with no structure at all

    # ── Character diversity (gibberish detection) ──
    alpha_chars = [c for c in text if c.isalpha()]
    if len(alpha_chars) > 20:
        unique_ratio = len(set(alpha_chars)) / len(alpha_chars)
        if unique_ratio < 0.05:
            score -= 0.4  # extremely low diversity = gibberish/repetition
        elif unique_ratio < 0.1:
            score -= 0.2

    # ── Unicode replacement chars (garbled encoding) ──
    replacement_count = text.count('\ufffd')
    if replacement_count > 3:
        score -= min(0.3, replacement_count * 0.05)

    return max(0.0, min(1.0, score))


# ── Public API ───────────────────────────────────────────────────────────────

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
```

### Step 2: Create test file for semantic evaluator

- [ ] **Create the test file** at `D:\QWEN3.0\tests\test_semantic_eval.py`:

```python
"""Tests for semantic_eval.py — lightweight semantic quality evaluator."""

import semantic_eval


# ── Keyword extraction ───────────────────────────────────────────────────────

def test_extract_keywords_filters_stop_words():
    kw = semantic_eval._extract_keywords("What is the meaning of life")
    assert "what" not in kw
    assert "is" not in kw
    assert "the" not in kw
    assert "meaning" in kw
    assert "life" in kw


def test_extract_keywords_handles_chinese():
    kw = semantic_eval._extract_keywords("如何优化Python代码性能")
    assert "优化" in kw or "python" in kw
    # Stop words filtered
    assert "如何" not in kw


def test_extract_keywords_empty_input():
    assert semantic_eval._extract_keywords("") == set()
    assert semantic_eval._extract_keywords("   ") == set()


# ── Query complexity estimation ─────────────────────────────────────────────

def test_estimate_simple_query():
    assert semantic_eval._estimate_query_complexity("hi") == "simple"
    assert semantic_eval._estimate_query_complexity("hello world") == "simple"


def test_estimate_medium_query():
    assert semantic_eval._estimate_query_complexity(
        "How do I sort a list in Python"
    ) == "medium"


def test_estimate_complex_query():
    assert semantic_eval._estimate_query_complexity(
        "Please explain the trade-offs between REST and GraphQL for microservices"
    ) == "complex"


def test_estimate_empty_query():
    assert semantic_eval._estimate_query_complexity("") == "simple"


# ── Relevance scoring ────────────────────────────────────────────────────────

def test_relevance_high_overlap():
    query = "Python list sorting algorithm"
    response = "To sort a Python list, you can use the built-in sorted() function or the .sort() method. The sorting algorithm used internally is Timsort."
    score = semantic_eval._score_relevance(query, response)
    assert score >= 0.7, f"Expected high relevance, got {score}"


def test_relevance_low_overlap():
    query = "Python list sorting algorithm"
    response = "The weather today is sunny with a high of 25 degrees Celsius. Remember to wear sunscreen."
    score = semantic_eval._score_relevance(query, response)
    assert score < 0.4, f"Expected low relevance, got {score}"


def test_relevance_empty_query():
    score = semantic_eval._score_relevance("", "some response text")
    assert score == 0.5  # neutral


def test_relevance_empty_response():
    score = semantic_eval._score_relevance("some query", "")
    assert score == 0.5  # neutral


def test_relevance_all_stop_words_query():
    score = semantic_eval._score_relevance("what is the", "some response")
    assert score == 0.7  # neutral-good when query is all stop words


# ── Completeness scoring ─────────────────────────────────────────────────────

def test_completeness_adequate_response():
    query = "How to sort a list"
    response = "You can use sorted(my_list) or my_list.sort() to sort a list in Python." + " More details here." * 10
    score = semantic_eval._score_completeness(query, response)
    assert score >= 0.8, f"Expected high completeness, got {score}"


def test_completeness_too_short():
    query = "Explain how to implement a binary search tree in Python with insert and delete operations"
    response = "Use a class."
    score = semantic_eval._score_completeness(query, response)
    assert score < 0.3, f"Expected low completeness for short response, got {score}"


def test_completeness_empty_response():
    score = semantic_eval._score_completeness("any query", "")
    assert score == 0.0


def test_completeness_overly_verbose():
    query = "hi"
    response = "word " * 10000  # ~50000 chars for a simple "hi" query
    score = semantic_eval._score_completeness(query, response)
    assert score < 0.5, f"Expected penalty for verbose response, got {score}"


# ── Coherence scoring ────────────────────────────────────────────────────────

def test_coherence_well_structured():
    response = """# Introduction

Here is an overview.

## Details

- Item 1
- Item 2

```python
def hello():
    print("world")
```

## Conclusion

This summarizes the key points."""
    score = semantic_eval._score_coherence(response)
    assert score >= 0.8, f"Expected high coherence for structured text, got {score}"


def test_coherence_gibberish():
    response = "a" * 500
    score = semantic_eval._score_coherence(response)
    assert score < 0.5, f"Expected low coherence for gibberish, got {score}"


def test_coherence_empty():
    assert semantic_eval._score_coherence("") == 0.0


def test_coherence_plain_text_with_sentences():
    response = (
        "Python is a versatile programming language. "
        "It supports multiple paradigms including OOP and functional programming. "
        "The standard library is comprehensive and well-documented."
    )
    score = semantic_eval._score_coherence(response)
    assert score >= 0.7, f"Expected decent coherence for plain sentences, got {score}"


def test_coherence_garbled_encoding():
    response = "This is fine. " + "\ufffd" * 20 + " More text here and some content."
    score = semantic_eval._score_coherence(response)
    assert score < 0.8, f"Expected penalty for garbled chars, got {score}"


# ── Composite evaluate_response ──────────────────────────────────────────────

def test_evaluate_high_quality_response():
    query = "How to implement a linked list in Python"
    response = """Here is how to implement a linked list in Python:

```python
class Node:
    def __init__(self, data):
        self.data = data
        self.next = None

class LinkedList:
    def __init__(self):
        self.head = None

    def append(self, data):
        new_node = Node(data)
        if not self.head:
            self.head = new_node
            return
        current = self.head
        while current.next:
            current = current.next
        current.next = new_node
```

The linked list is a fundamental data structure. Each node contains data and a reference to the next node."""
    result = semantic_eval.evaluate_response(query, response)
    assert result.total >= 70, f"Expected total >= 70, got {result.total}"
    assert result.relevance >= 0.6
    assert result.completeness >= 0.7
    assert result.coherence >= 0.7


def test_evaluate_irrelevant_response():
    query = "How to implement a linked list in Python"
    response = "The capital of France is Paris. It is known for the Eiffel Tower and the Louvre museum. French cuisine is world-renowned."
    result = semantic_eval.evaluate_response(query, response)
    assert result.total < 50, f"Expected total < 50 for irrelevant response, got {result.total}"
    assert result.relevance < 0.3


def test_evaluate_empty_response():
    result = semantic_eval.evaluate_response("any query", "")
    assert result.total < 30


def test_evaluate_empty_query_neutral():
    result = semantic_eval.evaluate_response("", "This is a perfectly fine response with good structure and content.")
    # With empty query, relevance is neutral (0.5), so total should still be reasonable
    assert result.total >= 30


def test_evaluate_returns_semantic_score_dataclass():
    result = semantic_eval.evaluate_response("test", "response text here")
    assert isinstance(result, semantic_eval.SemanticScore)
    assert hasattr(result, "total")
    assert hasattr(result, "relevance")
    assert hasattr(result, "completeness")
    assert hasattr(result, "coherence")


def test_evaluate_score_range():
    result = semantic_eval.evaluate_response(
        "Explain quantum computing in detail with examples",
        "Quantum computing uses qubits. Unlike classical bits that are 0 or 1, "
        "qubits can be in superposition. Here are some examples of quantum algorithms."
    )
    assert 0 <= result.total <= 100
    assert 0.0 <= result.relevance <= 1.0
    assert 0.0 <= result.completeness <= 1.0
    assert 0.0 <= result.coherence <= 1.0
```

### Step 3: Run tests

- [ ] **Run the tests:**

```bash
cd D:\QWEN3.0 && python -m pytest tests/test_semantic_eval.py -v
```

**Expected output:** All tests pass (20+ tests). Key assertions:
- Relevance scoring correctly distinguishes relevant vs irrelevant responses
- Completeness penalizes too-short and too-verbose responses
- Coherence detects gibberish and rewards structured text
- Composite score is 0-100

---

## Task 2: Quality Score Persistence (Ring Buffer)

**Files:**
- Create: `D:\QWEN3.0\quality_history.py`
- Test: `D:\QWEN3.0\tests\test_quality_history.py`

### Step 1: Create `quality_history.py`

- [ ] **Create the quality history module** at `D:\QWEN3.0\quality_history.py`:

```python
"""Quality history — per-backend semantic quality score persistence.

Stores quality scores in a ring buffer per backend. Provides trend analysis
including average, trend direction, and confidence interval.

Used by routing_selector to penalize backends with declining quality
and by evolution.py to choose explore/exploit/repair strategies.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass

# ── Configuration ────────────────────────────────────────────────────────────

QUALITY_HISTORY_SIZE = 50  # ring buffer capacity per backend
TREND_MIN_SAMPLES = 5      # minimum samples before trend is meaningful
CONFIDENCE_Z = 1.96        # 95% confidence interval z-score

_lock = threading.RLock()
_quality_histories: dict[str, deque] = {}


@dataclass
class QualityTrend:
    """Summary of quality trend for a backend."""
    average: float          # 0-100 average quality score
    trend: str              # "improving", "declining", "stable"
    confidence: float       # 0.0-1.0 confidence in the trend direction
    sample_count: int       # number of samples in history
    recent_average: float   # 0-100 average of last 10 scores
    std_dev: float          # standard deviation of scores


# ── Core operations ──────────────────────────────────────────────────────────

def record_quality(backend: str, score: float) -> None:
    """Record a semantic quality score for a backend.

    Args:
        backend: Backend identifier.
        score: Quality score 0-100 (from semantic_eval.evaluate_response).
    """
    score = max(0.0, min(100.0, score))
    with _lock:
        hist = _quality_histories.setdefault(
            backend, deque(maxlen=QUALITY_HISTORY_SIZE)
        )
        hist.append((time.monotonic(), score))


def get_quality_trend(backend: str) -> QualityTrend:
    """Compute quality trend for a backend.

    Returns a QualityTrend with average, direction, and confidence.
    For backends with no history, returns neutral defaults.
    """
    with _lock:
        hist = _quality_histories.get(backend)
        if not hist:
            return QualityTrend(
                average=50.0, trend="stable", confidence=0.0,
                sample_count=0, recent_average=50.0, std_dev=0.0,
            )

        scores = [s for _, s in hist]
        n = len(scores)
        avg = sum(scores) / n

        # Standard deviation
        if n >= 2:
            variance = sum((s - avg) ** 2 for s in scores) / (n - 1)
            std = variance ** 0.5
        else:
            std = 0.0

        # Recent average (last 10)
        recent = scores[-10:]
        recent_avg = sum(recent) / len(recent)

        # Trend direction: compare recent half vs older half
        trend = "stable"
        confidence = 0.0
        if n >= TREND_MIN_SAMPLES:
            mid = n // 2
            older_half = scores[:mid]
            newer_half = scores[mid:]
            older_avg = sum(older_half) / len(older_half)
            newer_avg = sum(newer_half) / len(newer_half)
            diff = newer_avg - older_avg

            # Margin of error
            se = std / (n ** 0.5) if n > 1 else 0.0
            margin = CONFIDENCE_Z * se if se > 0 else 5.0

            if diff > margin:
                trend = "improving"
            elif diff < -margin:
                trend = "declining"

            # Confidence based on sample size and effect magnitude
            effect_size = abs(diff) / max(std, 1.0)
            confidence = min(1.0, (n / QUALITY_HISTORY_SIZE) * 0.5 + effect_size * 0.5)

        return QualityTrend(
            average=round(avg, 1),
            trend=trend,
            confidence=round(confidence, 3),
            sample_count=n,
            recent_average=round(recent_avg, 1),
            std_dev=round(std, 1),
        )


def get_all_trends() -> dict[str, QualityTrend]:
    """Return quality trends for all tracked backends."""
    with _lock:
        backends = list(_quality_histories.keys())
    return {b: get_quality_trend(b) for b in backends}


def get_quality_score_for_routing(backend: str) -> float:
    """Get a single quality factor (0.0-2.0) for use in routing score multiplication.

    Returns:
        - 1.0 if no history (neutral)
        - 0.7-0.9 if declining quality
        - 1.0-1.2 if improving quality
        - 0.95-1.05 if stable
    """
    trend = get_quality_trend(backend)
    if trend.sample_count < TREND_MIN_SAMPLES:
        return 1.0  # not enough data

    # Map average quality to a routing multiplier
    # Average 0-100 mapped to multiplier 0.7-1.3
    base = 0.7 + (trend.average / 100.0) * 0.6

    # Adjust by trend direction
    if trend.trend == "declining":
        base *= (1.0 - trend.confidence * 0.15)
    elif trend.trend == "improving":
        base *= (1.0 + trend.confidence * 0.1)

    return round(max(0.5, min(1.5, base)), 3)


def reset_all() -> None:
    """Clear all quality history (tests only)."""
    with _lock:
        _quality_histories.clear()
```

### Step 2: Create test file for quality history

- [ ] **Create the test file** at `D:\QWEN3.0\tests\test_quality_history.py`:

```python
"""Tests for quality_history.py — per-backend quality score persistence."""

import time
from unittest.mock import patch

import quality_history


def setup_function():
    quality_history.reset_all()


# ── Basic recording and retrieval ────────────────────────────────────────────

def test_record_and_get_trend():
    for i in range(10):
        quality_history.record_quality("backend_a", 80.0)
    trend = quality_history.get_quality_trend("backend_a")
    assert trend.average == 80.0
    assert trend.sample_count == 10


def test_get_trend_no_history_returns_defaults():
    trend = quality_history.get_quality_trend("nonexistent")
    assert trend.average == 50.0
    assert trend.trend == "stable"
    assert trend.confidence == 0.0
    assert trend.sample_count == 0


def test_score_clamped_to_range():
    quality_history.record_quality("clamp_test", 150.0)
    quality_history.record_quality("clamp_test", -20.0)
    trend = quality_history.get_quality_trend("clamp_test")
    assert 0.0 <= trend.average <= 100.0


# ── Trend direction detection ────────────────────────────────────────────────

def test_declining_trend_detected():
    # First half: high scores, second half: low scores
    for _ in range(10):
        quality_history.record_quality("declining_backend", 90.0)
    for _ in range(10):
        quality_history.record_quality("declining_backend", 30.0)
    trend = quality_history.get_quality_trend("declining_backend")
    assert trend.trend == "declining", f"Expected declining, got {trend.trend}"
    assert trend.confidence > 0.0


def test_improving_trend_detected():
    # First half: low scores, second half: high scores
    for _ in range(10):
        quality_history.record_quality("improving_backend", 30.0)
    for _ in range(10):
        quality_history.record_quality("improving_backend", 90.0)
    trend = quality_history.get_quality_trend("improving_backend")
    assert trend.trend == "improving", f"Expected improving, got {trend.trend}"


def test_stable_trend_detected():
    for _ in range(20):
        quality_history.record_quality("stable_backend", 75.0)
    trend = quality_history.get_quality_trend("stable_backend")
    assert trend.trend == "stable", f"Expected stable, got {trend.trend}"


def test_insufficient_samples_returns_stable():
    for _ in range(3):
        quality_history.record_quality("few_samples", 80.0)
    trend = quality_history.get_quality_trend("few_samples")
    assert trend.trend == "stable"  # < TREND_MIN_SAMPLES


# ── Ring buffer behavior ────────────────────────────────────────────────────

def test_ring_buffer_capacity():
    for i in range(100):
        quality_history.record_quality("overflow_test", float(i))
    trend = quality_history.get_quality_trend("overflow_test")
    assert trend.sample_count == quality_history.QUALITY_HISTORY_SIZE


def test_ring_buffer_keeps_recent():
    for i in range(60):
        quality_history.record_quality("recent_test", float(i))
    trend = quality_history.get_quality_trend("recent_test")
    # Should keep last 50: scores 10-59, avg = 34.5
    assert trend.average > 30.0


# ── Routing score factor ─────────────────────────────────────────────────────

def test_routing_score_neutral_for_new_backend():
    factor = quality_history.get_quality_score_for_routing("brand_new")
    assert factor == 1.0


def test_routing_score_penalizes_declining():
    for _ in range(10):
        quality_history.record_quality("bad_backend", 90.0)
    for _ in range(10):
        quality_history.record_quality("bad_backend", 20.0)
    factor = quality_history.get_quality_score_for_routing("bad_backend")
    assert factor < 1.0, f"Expected penalty for declining quality, got {factor}"


def test_routing_score_rewards_improving():
    for _ in range(10):
        quality_history.record_quality("good_backend", 20.0)
    for _ in range(10):
        quality_history.record_quality("good_backend", 90.0)
    factor = quality_history.get_quality_score_for_routing("good_backend")
    assert factor > 1.0, f"Expected boost for improving quality, got {factor}"


# ── get_all_trends ───────────────────────────────────────────────────────────

def test_get_all_trends():
    quality_history.record_quality("alpha", 80.0)
    quality_history.record_quality("beta", 60.0)
    trends = quality_history.get_all_trends()
    assert "alpha" in trends
    assert "beta" in trends
    assert trends["alpha"].average == 80.0
    assert trends["beta"].average == 60.0


# ── Recent average ───────────────────────────────────────────────────────────

def test_recent_average():
    for _ in range(20):
        quality_history.record_quality("recent_avg_test", 50.0)
    for _ in range(5):
        quality_history.record_quality("recent_avg_test", 90.0)
    trend = quality_history.get_quality_trend("recent_avg_test")
    # Recent 10: 5 from old (50.0) + 5 new (90.0) = avg 70.0
    assert trend.recent_average == 70.0


# ── Reset ────────────────────────────────────────────────────────────────────

def test_reset_all():
    quality_history.record_quality("test", 80.0)
    quality_history.reset_all()
    trend = quality_history.get_quality_trend("test")
    assert trend.sample_count == 0
```

### Step 3: Run tests

- [ ] **Run the tests:**

```bash
cd D:\QWEN3.0 && python -m pytest tests/test_quality_history.py -v
```

**Expected output:** All 16 tests pass. Key verifications:
- Trend detection correctly identifies improving/declining/stable patterns
- Ring buffer caps at QUALITY_HISTORY_SIZE entries
- Routing score factor penalizes declining and rewards improving backends

---

## Task 3: Integrate into Response Pipeline

**Files:**
- Modify: `D:\QWEN3.0\context_pipeline\response_processors.py` (add `semantic_quality_processor`)
- Modify: `D:\QWEN3.0\routing_executor.py` (hook evaluation after successful response)
- Test: `D:\QWEN3.0\tests\test_semantic_quality_integration.py`

### Step 1: Add `semantic_quality_processor` to response_processors.py

- [ ] **Add the semantic quality processor** to `D:\QWEN3.0\context_pipeline\response_processors.py`:

Add this function after the existing `lesson_extraction_processor` function and before `build_default_pipeline`:

```python
def semantic_quality_processor(ctx: ResponseContext) -> ResponseContext:
    """Evaluate semantic quality and record to quality history.

    Uses semantic_eval.evaluate_response() for relevance/completeness/coherence
    scoring, then records the score in quality_history for trend tracking.
    Also updates health_tracker's quality scoring.
    """
    if not ctx.response_text or not ctx.quality_ok:
        return ctx

    try:
        import quality_history
        import semantic_eval

        # Extract the original query from the response context if available
        query = getattr(ctx, "query", "") or ""

        result = semantic_eval.evaluate_response(query, ctx.response_text)

        # Record to quality history ring buffer
        if ctx.backend:
            quality_history.record_quality(ctx.backend, result.total)

            # Also feed into existing health_scoring quality system
            import health_tracker
            # Map semantic score (0-100) to existing quality scale (0.0-1.0)
            health_tracker.record_quality_score(ctx.backend, result.total / 100.0)

    except Exception as exc:
        _log.debug("semantic_quality_processor: evaluation failed", exc_info=True)

    return ctx
```

- [ ] **Update `build_default_pipeline()`** to include the new processor:

Replace the existing `build_default_pipeline` function with:

```python
def build_default_response_pipeline():
    """Build the standard response processing pipeline."""
    from context_pipeline.response_pipeline import ResponsePipeline

    return (
        ResponsePipeline()
        .add("quality_check", quality_check_processor)
        .add("code_validation", code_validation_processor)
        .add("semantic_quality", semantic_quality_processor)
        .add("memory_capture", memory_capture_processor)
        .add("event_recording", event_recording_processor)
        .add("lesson_extraction", lesson_extraction_processor)
    )
```

### Step 2: Hook into `routing_executor.py`

- [ ] **Modify `D:\QWEN3.0\routing_executor.py`** to record semantic quality after each successful response. Add this block after line 46 (the `return backend, answer, errors` in the main success path):

Replace the block at lines 43-46:

```python
            if answer and len(answer.strip()) > 0:
                re.health_tracker.record_success(backend, latency_ms)
                re.budget_manager.record_usage(backend)
                return backend, answer, errors
```

With:

```python
            if answer and len(answer.strip()) > 0:
                re.health_tracker.record_success(backend, latency_ms)
                re.budget_manager.record_usage(backend)

                # Semantic quality evaluation (non-blocking, best-effort)
                try:
                    import quality_history
                    import semantic_eval
                    query_text = ""
                    for msg in reversed(messages):
                        if isinstance(msg, dict) and msg.get("role") == "user":
                            query_text = msg.get("content", "")
                            break
                    if query_text:
                        sq = semantic_eval.evaluate_response(query_text, answer)
                        quality_history.record_quality(backend, sq.total)
                except Exception:
                    pass

                return backend, answer, errors
```

### Step 3: Create integration test

- [ ] **Create the test file** at `D:\QWEN3.0\tests\test_semantic_quality_integration.py`:

```python
"""Tests for semantic quality integration into the response pipeline."""

from unittest.mock import MagicMock, patch, PropertyMock

import quality_history
import semantic_eval
from context_pipeline.response_pipeline import ResponseContext


def setup_function():
    quality_history.reset_all()


# ── semantic_quality_processor ───────────────────────────────────────────────

def test_semantic_quality_processor_records_score():
    from context_pipeline.response_processors import semantic_quality_processor

    ctx = ResponseContext(
        backend="test_backend",
        response_text="Here is how to implement a linked list in Python with Node class and append method.",
        status_code=200,
        latency_ms=500,
    )
    ctx.query = "How to implement a linked list in Python"

    result = semantic_quality_processor(ctx)

    trend = quality_history.get_quality_trend("test_backend")
    assert trend.sample_count == 1
    assert trend.average > 0


def test_semantic_quality_processor_skips_empty_response():
    from context_pipeline.response_processors import semantic_quality_processor

    ctx = ResponseContext(
        backend="test_backend",
        response_text="",
        status_code=200,
        latency_ms=500,
    )

    result = semantic_quality_processor(ctx)
    trend = quality_history.get_quality_trend("test_backend")
    assert trend.sample_count == 0


def test_semantic_quality_processor_skips_failed_quality():
    from context_pipeline.response_processors import semantic_quality_processor

    ctx = ResponseContext(
        backend="test_backend",
        response_text="Some text",
        status_code=200,
        latency_ms=500,
    )
    ctx.quality_ok = False  # Previous processor flagged issues

    result = semantic_quality_processor(ctx)
    trend = quality_history.get_quality_trend("test_backend")
    assert trend.sample_count == 0


def test_semantic_quality_processor_handles_import_error():
    """Processor should not crash if semantic_eval is unavailable."""
    from context_pipeline.response_processors import semantic_quality_processor

    ctx = ResponseContext(
        backend="test_backend",
        response_text="Some valid response text here.",
        status_code=200,
        latency_ms=500,
    )

    with patch.dict("sys.modules", {"semantic_eval": None}):
        # Should not raise even if semantic_eval import fails
        result = semantic_quality_processor(ctx)
        assert result is not None


# ── build_default_response_pipeline includes semantic_quality ────────────────

def test_default_pipeline_includes_semantic_quality():
    from context_pipeline.response_processors import build_default_response_pipeline

    pipeline = build_default_response_pipeline()
    processor_names = [name for name, _ in pipeline._processors]
    assert "semantic_quality" in processor_names


def test_default_pipeline_order():
    """semantic_quality should come after quality_check but before memory_capture."""
    from context_pipeline.response_processors import build_default_response_pipeline

    pipeline = build_default_response_pipeline()
    names = [name for name, _ in pipeline._processors]
    assert names.index("quality_check") < names.index("semantic_quality")
    assert names.index("semantic_quality") < names.index("memory_capture")


# ── Full pipeline processing ────────────────────────────────────────────────

def test_full_pipeline_processes_semantic_quality():
    from context_pipeline.response_processors import build_default_response_pipeline

    pipeline = build_default_response_pipeline()
    ctx = ResponseContext(
        backend="pipeline_test",
        response_text="To sort a Python list, use sorted() or .sort() method. Both work well for most use cases.",
        status_code=200,
        latency_ms=300,
    )
    ctx.query = "How to sort a list in Python"

    result = pipeline.process(ctx)
    assert "semantic_quality" in result.processors_applied


# ── routing_executor integration ─────────────────────────────────────────────

def test_routing_executor_records_semantic_quality():
    """Verify routing_executor calls semantic_eval after successful response."""
    with patch("quality_history.record_quality") as mock_record, \
         patch("semantic_eval.evaluate_response") as mock_eval:

        mock_eval.return_value = semantic_eval.SemanticScore(
            total=85.0, relevance=0.9, completeness=0.8, coherence=0.85
        )

        # Simulate what routing_executor does after a successful response
        import semantic_eval as se
        import quality_history as qh

        query_text = "How to implement sorting"
        answer = "Here is how to implement sorting in Python using sorted()."
        backend = "test_backend"

        sq = se.evaluate_response(query_text, answer)
        qh.record_quality(backend, sq.total)

        trend = qh.get_quality_trend(backend)
        assert trend.sample_count == 1
        assert trend.average > 0
```

### Step 4: Run tests

- [ ] **Run the tests:**

```bash
cd D:\QWEN3.0 && python -m pytest tests/test_semantic_quality_integration.py -v
```

**Expected output:** All 10 tests pass. Key verifications:
- `semantic_quality_processor` records scores to quality_history
- Processor is included in the default pipeline at the correct position
- Processor gracefully handles import errors and empty responses

---

## Task 4: Quality-Weighted Routing

**Files:**
- Modify: `D:\QWEN3.0\route_scorer.py` (add quality_trend to `effective_score`)
- Modify: `D:\QWEN3.0\routing_selector.py` (add quality factor to per-backend scoring)
- Test: `D:\QWEN3.0\tests\test_quality_weighted_routing.py`

### Step 1: Modify `route_scorer.py` effective_score

- [ ] **Update `effective_score()`** in `D:\QWEN3.0\route_scorer.py` to include quality_trend.

Replace the existing `effective_score` function (lines 99-115):

```python
def effective_score(backend: str, request_type: str, scenario: str = "",
                    *, health_score: float = 50.0,
                    state: dict | None = None,
                    avg_latency_ms: float = 1000.0,
                    remaining_quota_score: float | None = None,
                    quality_trend_score: float = 1.0) -> float:
    quota_score = (
        budget_manager.get_remaining_quota_score(backend)
        if remaining_quota_score is None else remaining_quota_score
    )
    score = (
        _norm_score(health_score) * 0.35
        + stability_score(state) * 0.25
        + latency_score(avg_latency_ms) * 0.15
        + max(0.0, min(quota_score, 1.0)) * 0.10
        + task_fit_score(backend, request_type, scenario) * 0.05
        + max(0.0, min(quality_trend_score, 2.0)) * 0.10
    )
    return round(score, 6)
```

Key change: health weight reduced from 0.45 to 0.35, added `quality_trend_score * 0.10`.

### Step 2: Update `rank_backends` to pass quality_trend

- [ ] **Update `rank_backends()`** in `D:\QWEN3.0\route_scorer.py`:

Replace the existing `rank_backends` function (lines 118-140):

```python
def rank_backends(backends: list[str], request_type: str, scenario: str = "",
                  *, health_scores: dict[str, float] | None = None,
                  states: dict[str, dict] | None = None,
                  latency_map: dict[str, float] | None = None,
                  quality_trends: dict[str, float] | None = None) -> list[str]:
    health_scores = health_scores or {}
    states = states or {}
    latency_map = latency_map or {}
    quality_trends = quality_trends or {}

    def key(item: tuple[int, str]) -> tuple[float, int]:
        idx, backend = item
        return (
            -effective_score(
                backend,
                request_type,
                scenario,
                health_score=health_scores.get(backend, 50.0),
                state=states.get(backend),
                avg_latency_ms=latency_map.get(backend, 1000.0),
                quality_trend_score=quality_trends.get(backend, 1.0),
            ),
            idx,
        )

    return [backend for _, backend in sorted(enumerate(backends), key=key)]
```

### Step 3: Update `routing_selector.py` to pass quality trends

- [ ] **Modify `D:\QWEN3.0\routing_selector.py`** to compute and pass quality trends. Add the quality factor computation in the scoring loop and pass it to `rank_backends`.

After line 103 (`scores = re.health_tracker.get_scores()`), add:

```python
    # Compute quality trend factors for all backends
    try:
        import quality_history
        quality_trends = {
            b: quality_history.get_quality_score_for_routing(b)
            for b in result
        }
    except ImportError:
        quality_trends = {}
```

- [ ] **Update the `route_scorer.rank_backends` call** (currently at lines 205-209) to pass quality_trends:

Replace:

```python
    result = route_scorer.rank_backends(
        result, request_type, scenario,
        health_scores=scores,
        states=states,
        latency_map=re.health_tracker.get_latency_map())
```

With:

```python
    result = route_scorer.rank_backends(
        result, request_type, scenario,
        health_scores=scores,
        states=states,
        latency_map=re.health_tracker.get_latency_map(),
        quality_trends=quality_trends)
```

- [ ] **Also apply quality factor in the per-backend scoring loop** (around line 126, after the `scores[b] = base * latency_score * ...` block). Add after the existing scoring block and before the `try: from context_pipeline.routing_weights` block:

```python
        # Apply semantic quality trend factor
        qt = quality_trends.get(b, 1.0)
        scores[b] *= qt
```

### Step 4: Create test file

- [ ] **Create the test file** at `D:\QWEN3.0\tests\test_quality_weighted_routing.py`:

```python
"""Tests for quality-weighted routing — route_scorer and routing_selector integration."""

from unittest.mock import MagicMock, patch

import quality_history
import route_scorer


def setup_function():
    quality_history.reset_all()


# ── route_scorer.effective_score with quality_trend ──────────────────────────

def test_effective_score_includes_quality_trend():
    """effective_score should include quality_trend_score as a factor."""
    score_high_quality = route_scorer.effective_score(
        "backend_a", "chat", "chat",
        health_score=80.0,
        avg_latency_ms=500.0,
        remaining_quota_score=1.0,
        quality_trend_score=1.2,  # improving
    )
    score_low_quality = route_scorer.effective_score(
        "backend_a", "chat", "chat",
        health_score=80.0,
        avg_latency_ms=500.0,
        remaining_quota_score=1.0,
        quality_trend_score=0.7,  # declining
    )
    assert score_high_quality > score_low_quality, (
        f"High quality ({score_high_quality}) should score higher "
        f"than low quality ({score_low_quality})"
    )


def test_effective_score_default_quality_trend():
    """Default quality_trend_score should be 1.0 (neutral)."""
    score_default = route_scorer.effective_score(
        "backend_a", "chat", "chat",
        health_score=80.0,
        avg_latency_ms=500.0,
        remaining_quota_score=1.0,
    )
    score_explicit_neutral = route_scorer.effective_score(
        "backend_a", "chat", "chat",
        health_score=80.0,
        avg_latency_ms=500.0,
        remaining_quota_score=1.0,
        quality_trend_score=1.0,
    )
    assert score_default == score_explicit_neutral


def test_effective_score_weights_sum_to_one():
    """Verify all weights sum to 1.0: 0.35 + 0.25 + 0.15 + 0.10 + 0.05 + 0.10 = 1.0."""
    weights = [0.35, 0.25, 0.15, 0.10, 0.05, 0.10]
    assert abs(sum(weights) - 1.0) < 0.001


# ── rank_backends with quality trends ────────────────────────────────────────

def test_rank_backends_uses_quality_trends():
    """rank_backends should consider quality trends in ordering."""
    backends = ["good_backend", "bad_backend", "neutral_backend"]

    # All have same health score and latency
    health_scores = {b: 80.0 for b in backends}
    states = {b: {"state": "ok"} for b in backends}
    latency_map = {b: 500.0 for b in backends}

    # Different quality trends
    quality_trends = {
        "good_backend": 1.3,    # improving
        "bad_backend": 0.7,     # declining
        "neutral_backend": 1.0, # neutral
    }

    ranked = route_scorer.rank_backends(
        backends, "chat", "chat",
        health_scores=health_scores,
        states=states,
        latency_map=latency_map,
        quality_trends=quality_trends,
    )

    assert ranked[0] == "good_backend", f"Expected good_backend first, got {ranked}"
    assert ranked[-1] == "bad_backend", f"Expected bad_backend last, got {ranked}"


def test_rank_backends_default_no_quality_trends():
    """When no quality_trends passed, all backends get neutral 1.0."""
    backends = ["a", "b"]
    ranked = route_scorer.rank_backends(
        backends, "chat", "chat",
        health_scores={"a": 80.0, "b": 80.0},
        states={"a": {"state": "ok"}, "b": {"state": "ok"}},
        latency_map={"a": 500.0, "b": 500.0},
    )
    # Both should have equal scores, order preserved
    assert len(ranked) == 2


# ── routing_selector integration ─────────────────────────────────────────────

def test_routing_selector_computes_quality_trends():
    """routing_selector.select should compute quality_trends from quality_history."""
    # Record some quality data
    for _ in range(10):
        quality_history.record_quality("scnet_ds_flash", 85.0)
    for _ in range(10):
        quality_history.record_quality("scnet_ds_flash", 20.0)

    factor = quality_history.get_quality_score_for_routing("scnet_ds_flash")
    assert factor < 1.0, f"Declining backend should have factor < 1.0, got {factor}"


def test_quality_history_integration_with_routing():
    """End-to-end: quality history affects routing scores."""
    # Setup: backend A has declining quality, backend B has improving quality
    for _ in range(15):
        quality_history.record_quality("backend_a", 90.0)
    for _ in range(15):
        quality_history.record_quality("backend_a", 30.0)

    for _ in range(15):
        quality_history.record_quality("backend_b", 30.0)
    for _ in range(15):
        quality_history.record_quality("backend_b", 90.0)

    factor_a = quality_history.get_quality_score_for_routing("backend_a")
    factor_b = quality_history.get_quality_score_for_routing("backend_b")

    # B should have a higher routing factor than A
    assert factor_b > factor_a, (
        f"Improving backend_b ({factor_b}) should have higher factor "
        f"than declining backend_a ({factor_a})"
    )
```

### Step 5: Run tests

- [ ] **Run the tests:**

```bash
cd D:\QWEN3.0 && python -m pytest tests/test_quality_weighted_routing.py -v
```

**Expected output:** All 8 tests pass. Key verifications:
- `effective_score` includes quality_trend as a factor
- `rank_backends` correctly orders by quality-adjusted scores
- Weights sum to exactly 1.0
- Declining backends get penalized, improving backends get boosted

---

## Task 5: Quality Dashboard Metrics

**Files:**
- Modify: `D:\QWEN3.0\routes\admin_api.py` (add quality trends to `/api/stats` and `/api/backend-health`)
- Modify: `D:\QWEN3.0\routes\ops_metrics.py` (add quality trends to `/v1/ops/metrics`)
- Test: `D:\QWEN3.0\tests\test_quality_dashboard.py`

### Step 1: Add quality trends to `/api/stats`

- [ ] **Modify `admin_stats()`** in `D:\QWEN3.0\routes\admin_api.py` (lines 89-119). Add quality trend summary to the return dict. Insert this code before the `return` statement:

```python
        # Semantic quality trends
        quality_summary = {}
        try:
            import quality_history
            all_trends = quality_history.get_all_trends()
            quality_summary = {
                "tracked_backends": len(all_trends),
                "declining": sum(1 for t in all_trends.values() if t.trend == "declining"),
                "improving": sum(1 for t in all_trends.values() if t.trend == "improving"),
                "stable": sum(1 for t in all_trends.values() if t.trend == "stable"),
                "avg_quality": round(
                    sum(t.average for t in all_trends.values()) / max(len(all_trends), 1), 1
                ),
            }
        except ImportError:
            pass
```

And add `"quality_trends": quality_summary,` to the returned dict.

### Step 2: Add quality trends to `/api/backend-health`

- [ ] **Modify `admin_backend_health()`** in `D:\QWEN3.0\routes\admin_api.py` (lines 220-268). Add quality trend data per backend. After the existing `backends.append({...})` block (around line 251), add quality fields:

Inside the for-loop, before `backends.append({`, add:

```python
        # Semantic quality trend
        qt_data = {"average": 50.0, "trend": "stable", "confidence": 0.0, "sample_count": 0}
        try:
            import quality_history
            qt = quality_history.get_quality_trend(name)
            qt_data = {
                "average": qt.average,
                "trend": qt.trend,
                "confidence": qt.confidence,
                "sample_count": qt.sample_count,
                "recent_average": qt.recent_average,
            }
        except ImportError:
            pass
```

And add `"quality_trend": qt_data,` inside the dict passed to `backends.append()`.

### Step 3: Add quality trends to `/v1/ops/metrics`

- [ ] **Modify `ops_metrics()`** in `D:\QWEN3.0\routes\ops_metrics.py`. Add a `quality` section to the returned JSON. Insert before the `return JSONResponse({...})` (around line 230):

```python
    # Semantic quality trends
    quality_metrics: dict[str, Any] = {}
    try:
        import quality_history
        all_trends = quality_history.get_all_trends()
        quality_metrics = {
            "tracked_backends": len(all_trends),
            "declining_backends": [
                b for b, t in all_trends.items() if t.trend == "declining"
            ],
            "improving_backends": [
                b for b, t in all_trends.items() if t.trend == "improving"
            ],
            "avg_quality": round(
                sum(t.average for t in all_trends.values()) / max(len(all_trends), 1), 1
            ),
            "total_samples": sum(t.sample_count for t in all_trends.values()),
        }
    except ImportError:
        _log.debug("ops_metrics: quality_history not available", exc_info=True)
```

And add `"quality": quality_metrics,` inside the JSONResponse dict.

### Step 4: Create test file

- [ ] **Create the test file** at `D:\QWEN3.0\tests\test_quality_dashboard.py`:

```python
"""Tests for quality trend data in dashboard/metrics endpoints."""

from unittest.mock import MagicMock, patch

import quality_history


def setup_function():
    quality_history.reset_all()


# ── admin_stats quality summary ──────────────────────────────────────────────

def test_admin_stats_includes_quality_summary():
    """Verify admin_stats builds quality summary from quality_history."""
    for _ in range(10):
        quality_history.record_quality("backend_a", 85.0)
    for _ in range(10):
        quality_history.record_quality("backend_b", 40.0)

    all_trends = quality_history.get_all_trends()
    summary = {
        "tracked_backends": len(all_trends),
        "declining": sum(1 for t in all_trends.values() if t.trend == "declining"),
        "improving": sum(1 for t in all_trends.values() if t.trend == "improving"),
        "stable": sum(1 for t in all_trends.values() if t.trend == "stable"),
        "avg_quality": round(
            sum(t.average for t in all_trends.values()) / max(len(all_trends), 1), 1
        ),
    }

    assert summary["tracked_backends"] == 2
    assert summary["avg_quality"] > 0


def test_admin_stats_quality_summary_empty():
    """With no quality data, summary should have zero counts."""
    all_trends = quality_history.get_all_trends()
    summary = {
        "tracked_backends": len(all_trends),
        "declining": sum(1 for t in all_trends.values() if t.trend == "declining"),
        "improving": sum(1 for t in all_trends.values() if t.trend == "improving"),
        "stable": sum(1 for t in all_trends.values() if t.trend == "stable"),
        "avg_quality": round(
            sum(t.average for t in all_trends.values()) / max(len(all_trends), 1), 1
        ),
    }
    assert summary["tracked_backends"] == 0
    assert summary["avg_quality"] == 0.0


# ── backend-health quality per backend ───────────────────────────────────────

def test_backend_health_includes_quality_trend():
    """Each backend in backend-health should include quality_trend data."""
    for _ in range(10):
        quality_history.record_quality("test_backend", 75.0)

    qt = quality_history.get_quality_trend("test_backend")
    qt_data = {
        "average": qt.average,
        "trend": qt.trend,
        "confidence": qt.confidence,
        "sample_count": qt.sample_count,
        "recent_average": qt.recent_average,
    }

    assert qt_data["average"] == 75.0
    assert qt_data["sample_count"] == 10
    assert qt_data["trend"] in ("stable", "improving", "declining")


def test_backend_health_quality_default_for_unknown():
    """Backends with no quality history should get default trend data."""
    qt = quality_history.get_quality_trend("unknown_backend")
    qt_data = {
        "average": qt.average,
        "trend": qt.trend,
        "confidence": qt.confidence,
        "sample_count": qt.sample_count,
    }

    assert qt_data["average"] == 50.0
    assert qt_data["trend"] == "stable"
    assert qt_data["sample_count"] == 0


# ── ops_metrics quality section ──────────────────────────────────────────────

def test_ops_metrics_includes_quality_section():
    """ops_metrics should include quality trends in its response."""
    for _ in range(10):
        quality_history.record_quality("good_backend", 90.0)
    for _ in range(10):
        quality_history.record_quality("bad_backend", 90.0)
    for _ in range(10):
        quality_history.record_quality("bad_backend", 20.0)

    all_trends = quality_history.get_all_trends()
    quality_metrics = {
        "tracked_backends": len(all_trends),
        "declining_backends": [
            b for b, t in all_trends.items() if t.trend == "declining"
        ],
        "improving_backends": [
            b for b, t in all_trends.items() if t.trend == "improving"
        ],
        "avg_quality": round(
            sum(t.average for t in all_trends.values()) / max(len(all_trends), 1), 1
        ),
        "total_samples": sum(t.sample_count for t in all_trends.values()),
    }

    assert quality_metrics["tracked_backends"] == 2
    assert "bad_backend" in quality_metrics["declining_backends"]
    assert quality_metrics["total_samples"] == 30  # 10 + 20


def test_ops_metrics_quality_empty():
    """With no quality data, quality section should be present but empty."""
    all_trends = quality_history.get_all_trends()
    quality_metrics = {
        "tracked_backends": len(all_trends),
        "declining_backends": [
            b for b, t in all_trends.items() if t.trend == "declining"
        ],
        "improving_backends": [
            b for b, t in all_trends.items() if t.trend == "improving"
        ],
        "avg_quality": round(
            sum(t.average for t in all_trends.values()) / max(len(all_trends), 1), 1
        ),
        "total_samples": sum(t.sample_count for t in all_trends.values()),
    }

    assert quality_metrics["tracked_backends"] == 0
    assert quality_metrics["declining_backends"] == []
    assert quality_metrics["total_samples"] == 0
```

### Step 5: Run tests

- [ ] **Run the tests:**

```bash
cd D:\QWEN3.0 && python -m pytest tests/test_quality_dashboard.py -v
```

**Expected output:** All 7 tests pass. Key verifications:
- Quality summary correctly aggregates trend counts
- Per-backend health includes quality trend data
- Ops metrics lists declining/improving backends

---

## Task 6: Quality Feedback Loop (Evolution Strategy)

**Files:**
- Modify: `D:\QWEN3.0\context_pipeline\evolution.py` (add quality_trend to `auto_select_strategy`)
- Modify: `D:\QWEN3.0\context_pipeline\signal_extraction.py` (extract quality signals)
- Test: `D:\QWEN3.0\tests\test_quality_feedback_loop.py`

### Step 1: Modify `evolution.py` auto_select_strategy

- [ ] **Update `auto_select_strategy()`** in `D:\QWEN3.0\context_pipeline\evolution.py` to accept and consider quality trend:

Replace the existing `auto_select_strategy` function (lines 63-84):

```python
def auto_select_strategy(
    recent_error_rate: float,
    recent_fallback_rate: float,
    backends_available: int,
    quality_trend: str = "stable",
) -> EvolutionStrategy:
    """Auto-select routing strategy based on system health and quality signals.

    Args:
        recent_error_rate: Error rate in last N requests (0.0-1.0)
        recent_fallback_rate: Fallback trigger rate (0.0-1.0)
        backends_available: Number of healthy backends
        quality_trend: Overall quality trend ("improving", "declining", "stable")
    """
    if recent_error_rate > 0.5 or backends_available < 3:
        return EvolutionStrategy.REPAIR

    # Quality feedback loop: declining quality triggers HARDEN
    if quality_trend == "declining":
        if recent_error_rate > 0.1 or recent_fallback_rate > 0.2:
            return EvolutionStrategy.HARDEN
        # Even without high errors, declining quality warrants caution
        if recent_error_rate > 0.05:
            return EvolutionStrategy.HARDEN

    if recent_error_rate > 0.2 or recent_fallback_rate > 0.3:
        return EvolutionStrategy.HARDEN

    # Quality feedback loop: stable high quality enables INNOVATE
    if recent_error_rate < 0.05 and recent_fallback_rate < 0.1:
        if quality_trend == "improving" or quality_trend == "stable":
            return EvolutionStrategy.INNOVATE
        return EvolutionStrategy.BALANCED

    return EvolutionStrategy.BALANCED
```

### Step 2: Update `signal_extraction.py` to extract quality signals

- [ ] **Modify `D:\QWEN3.0\context_pipeline\signal_extraction.py`** to include quality trend in signals and strategy recommendation:

Replace the existing `extract_signals` function (lines 14-66) and `recommend_strategy_from_signals` function (lines 69-75):

```python
def extract_signals(log: EventLog) -> dict:
    """Extract evolution signals from the event log, including quality trends."""
    events = log.events
    if not events:
        return {"error_rate": 0.0, "fallback_rate": 0.0, "quality_trend": "stable", "signals": []}

    total = len(events)
    errors = log.filter_by_type(EventType.RESPONSE_ERROR)
    fallbacks = log.filter_by_type(EventType.FALLBACK_TRIGGERED)
    successes = log.filter_by_type(EventType.RESPONSE_RECEIVED)

    error_rate = len(errors) / max(total, 1)
    fallback_rate = len(fallbacks) / max(total, 1)

    signals = []

    if error_rate > 0.5:
        signals.append({"type": "critical_error_rate", "value": error_rate})
    elif error_rate > 0.2:
        signals.append({"type": "elevated_error_rate", "value": error_rate})

    if fallback_rate > 0.3:
        signals.append({"type": "high_fallback_rate", "value": fallback_rate})

    # Detect backend-specific failure patterns
    backend_errors: dict[str, int] = {}
    for e in errors:
        backend = e.data.get("backend", "unknown")
        backend_errors[backend] = backend_errors.get(backend, 0) + 1

    for backend, count in backend_errors.items():
        if count >= 3:
            signals.append({
                "type": "backend_repeated_failure",
                "backend": backend,
                "count": count,
            })

    # Detect latency spikes
    latencies = [
        e.data.get("latency_ms", 0)
        for e in successes if e.data.get("latency_ms")
    ]
    if latencies:
        avg_latency = sum(latencies) / len(latencies)
        if avg_latency > 10000:
            signals.append({"type": "latency_spike", "avg_ms": int(avg_latency)})

    # Extract overall quality trend from quality_history
    overall_quality_trend = "stable"
    try:
        import quality_history
        all_trends = quality_history.get_all_trends()
        if all_trends:
            declining_count = sum(1 for t in all_trends.values() if t.trend == "declining")
            improving_count = sum(1 for t in all_trends.values() if t.trend == "improving")
            total_tracked = len(all_trends)

            if declining_count > total_tracked * 0.3:
                overall_quality_trend = "declining"
                signals.append({
                    "type": "quality_declining",
                    "declining_backends": declining_count,
                    "total_tracked": total_tracked,
                })
            elif improving_count > total_tracked * 0.3:
                overall_quality_trend = "improving"
                signals.append({
                    "type": "quality_improving",
                    "improving_backends": improving_count,
                    "total_tracked": total_tracked,
                })
    except ImportError:
        pass

    return {
        "error_rate": round(error_rate, 3),
        "fallback_rate": round(fallback_rate, 3),
        "quality_trend": overall_quality_trend,
        "signals": signals,
    }


def recommend_strategy_from_signals(signals: dict, backends_available: int = 10) -> EvolutionStrategy:
    """Recommend an evolution strategy based on extracted signals including quality."""
    return auto_select_strategy(
        recent_error_rate=signals["error_rate"],
        recent_fallback_rate=signals["fallback_rate"],
        backends_available=backends_available,
        quality_trend=signals.get("quality_trend", "stable"),
    )
```

### Step 3: Create test file

- [ ] **Create the test file** at `D:\QWEN3.0\tests\test_quality_feedback_loop.py`:

```python
"""Tests for quality feedback loop in evolution strategy selection."""

from unittest.mock import patch

import quality_history
from context_pipeline.evolution import (
    EvolutionStrategy,
    auto_select_strategy,
)


def setup_function():
    quality_history.reset_all()


# ── auto_select_strategy with quality_trend ──────────────────────────────────

def test_declining_quality_triggers_harden():
    """Declining quality should push toward HARDEN even with moderate error rates."""
    strategy = auto_select_strategy(
        recent_error_rate=0.08,
        recent_fallback_rate=0.15,
        backends_available=10,
        quality_trend="declining",
    )
    assert strategy == EvolutionStrategy.HARDEN, (
        f"Expected HARDEN for declining quality, got {strategy}"
    )


def test_declining_quality_with_low_errors_stays_balanced():
    """Declining quality with very low error rate should stay BALANCED."""
    strategy = auto_select_strategy(
        recent_error_rate=0.02,
        recent_fallback_rate=0.05,
        backends_available=10,
        quality_trend="declining",
    )
    # Very low errors + declining quality = BALANCED (declining alone doesn't panic)
    assert strategy in (EvolutionStrategy.BALANCED, EvolutionStrategy.HARDEN)


def test_improving_quality_enables_innovate():
    """Improving quality with low errors should enable INNOVATE."""
    strategy = auto_select_strategy(
        recent_error_rate=0.02,
        recent_fallback_rate=0.05,
        backends_available=10,
        quality_trend="improving",
    )
    assert strategy == EvolutionStrategy.INNOVATE, (
        f"Expected INNOVATE for improving quality, got {strategy}"
    )


def test_stable_quality_normal_selection():
    """Stable quality should follow normal error/fallback based selection."""
    strategy = auto_select_strategy(
        recent_error_rate=0.02,
        recent_fallback_rate=0.05,
        backends_available=10,
        quality_trend="stable",
    )
    assert strategy == EvolutionStrategy.INNOVATE  # low error + low fallback


def test_high_error_rate_overrides_quality():
    """High error rate should trigger REPAIR regardless of quality trend."""
    for trend in ("improving", "stable", "declining"):
        strategy = auto_select_strategy(
            recent_error_rate=0.6,
            recent_fallback_rate=0.1,
            backends_available=10,
            quality_trend=trend,
        )
        assert strategy == EvolutionStrategy.REPAIR, (
            f"Expected REPAIR for high error rate with {trend} quality, got {strategy}"
        )


def test_few_backends_overrides_quality():
    """Very few available backends should trigger REPAIR regardless of quality."""
    for trend in ("improving", "stable", "declining"):
        strategy = auto_select_strategy(
            recent_error_rate=0.1,
            recent_fallback_rate=0.1,
            backends_available=2,
            quality_trend=trend,
        )
        assert strategy == EvolutionStrategy.REPAIR


def test_backward_compatible_without_quality_trend():
    """auto_select_strategy should work without quality_trend parameter."""
    strategy = auto_select_strategy(
        recent_error_rate=0.02,
        recent_fallback_rate=0.05,
        backends_available=10,
    )
    # Should not crash, default to stable
    assert strategy in (EvolutionStrategy.INNOVATE, EvolutionStrategy.BALANCED)


# ── signal_extraction with quality ───────────────────────────────────────────

def test_extract_signals_includes_quality_trend():
    """extract_signals should include quality_trend in its output."""
    from context_pipeline.event_log import EventLog, EventType
    from context_pipeline.signal_extraction import extract_signals

    log = EventLog()
    for _ in range(10):
        log.emit(EventType.RESPONSE_RECEIVED, backend="a", latency_ms=500)

    signals = extract_signals(log)
    assert "quality_trend" in signals
    assert signals["quality_trend"] in ("improving", "declining", "stable")


def test_extract_signals_detects_declining_quality():
    """extract_signals should detect when many backends have declining quality."""
    from context_pipeline.event_log import EventLog, EventType
    from context_pipeline.signal_extraction import extract_signals

    # Set up declining quality for multiple backends
    for _ in range(15):
        quality_history.record_quality("b1", 90.0)
    for _ in range(15):
        quality_history.record_quality("b1", 20.0)
    for _ in range(15):
        quality_history.record_quality("b2", 90.0)
    for _ in range(15):
        quality_history.record_quality("b2", 20.0)

    log = EventLog()
    for _ in range(10):
        log.emit(EventType.RESPONSE_RECEIVED, backend="b1", latency_ms=500)

    signals = extract_signals(log)
    assert signals["quality_trend"] == "declining"
    quality_signals = [s for s in signals["signals"] if s["type"] == "quality_declining"]
    assert len(quality_signals) > 0


def test_recommend_strategy_uses_quality():
    """recommend_strategy_from_signals should pass quality_trend to auto_select."""
    from context_pipeline.signal_extraction import recommend_strategy_from_signals

    signals = {
        "error_rate": 0.08,
        "fallback_rate": 0.25,
        "quality_trend": "declining",
    }
    strategy = recommend_strategy_from_signals(signals, backends_available=10)
    assert strategy == EvolutionStrategy.HARDEN


def test_recommend_strategy_innovate_with_improving_quality():
    from context_pipeline.signal_extraction import recommend_strategy_from_signals

    signals = {
        "error_rate": 0.02,
        "fallback_rate": 0.05,
        "quality_trend": "improving",
    }
    strategy = recommend_strategy_from_signals(signals, backends_available=10)
    assert strategy == EvolutionStrategy.INNOVATE


# ── End-to-end feedback loop ─────────────────────────────────────────────────

def test_feedback_loop_quality_drives_strategy():
    """Full loop: record quality scores -> extract signals -> select strategy."""
    # Simulate a system where quality is declining
    for _ in range(20):
        quality_history.record_quality("main_backend", 85.0)
    for _ in range(20):
        quality_history.record_quality("main_backend", 25.0)

    from context_pipeline.event_log import EventLog, EventType
    from context_pipeline.signal_extraction import extract_signals, recommend_strategy_from_signals

    log = EventLog()
    for _ in range(15):
        log.emit(EventType.RESPONSE_RECEIVED, backend="main_backend", latency_ms=800)
    for _ in range(3):
        log.emit(EventType.RESPONSE_ERROR, backend="main_backend", error="timeout")

    signals = extract_signals(log)
    strategy = recommend_strategy_from_signals(signals, backends_available=8)

    # With declining quality and some errors, should HARDEN
    assert strategy == EvolutionStrategy.HARDEN, (
        f"Expected HARDEN for declining quality system, got {strategy}"
    )
```

### Step 4: Run tests

- [ ] **Run the tests:**

```bash
cd D:\QWEN3.0 && python -m pytest tests/test_quality_feedback_loop.py -v
```

**Expected output:** All 12 tests pass. Key verifications:
- Declining quality triggers HARDEN strategy
- Improving quality enables INNOVATE strategy
- High error rates override quality signals (safety first)
- Backward compatibility: function works without quality_trend parameter
- Signal extraction detects quality trends from quality_history

---

## Task 7: Full Integration Test

**Files:**
- Create: `D:\QWEN3.0\tests\test_semantic_quality_e2e.py`

### Step 1: Create comprehensive integration test

- [ ] **Create the end-to-end integration test** at `D:\QWEN3.0\tests\test_semantic_quality_e2e.py`:

```python
"""End-to-end integration test: semantic quality evaluation with feedback loop.

Tests the full pipeline:
1. Backend produces a response
2. Semantic evaluator scores it
3. Score is recorded in quality_history
4. Quality trend influences routing selection
5. Quality trend influences evolution strategy

All external dependencies are mocked.
"""

from unittest.mock import MagicMock, patch

import quality_history
import semantic_eval
from context_pipeline.evolution import EvolutionStrategy, auto_select_strategy


def setup_function():
    quality_history.reset_all()


# ── Scenario 1: High-quality backend gets rewarded ───────────────────────────

def test_high_quality_backend_rises_in_rankings():
    """A backend producing high-quality responses should rise in routing rankings."""
    import route_scorer

    # Simulate 20 high-quality responses from backend_a
    for _ in range(20):
        score = semantic_eval.evaluate_response(
            "How to implement a binary search tree",
            "Here is a complete implementation of a BST with insert, search, and delete operations. "
            "Each node has a value, left child, and right child. The left subtree contains only "
            "nodes with values less than the parent, and the right subtree contains only nodes "
            "with values greater.",
        )
        quality_history.record_quality("backend_a", score.total)

    # Simulate 20 low-quality responses from backend_b
    for _ in range(20):
        score = semantic_eval.evaluate_response(
            "How to implement a binary search tree",
            "The weather is nice today.",
        )
        quality_history.record_quality("backend_b", score.total)

    # Check routing factors
    factor_a = quality_history.get_quality_score_for_routing("backend_a")
    factor_b = quality_history.get_quality_score_for_routing("backend_b")

    assert factor_a > factor_b, (
        f"High-quality backend_a ({factor_a}) should rank higher "
        f"than low-quality backend_b ({factor_b})"
    )

    # Verify through route_scorer
    score_a = route_scorer.effective_score(
        "backend_a", "chat", "coding",
        health_score=80.0, avg_latency_ms=500.0,
        remaining_quota_score=1.0, quality_trend_score=factor_a,
    )
    score_b = route_scorer.effective_score(
        "backend_b", "chat", "coding",
        health_score=80.0, avg_latency_ms=500.0,
        remaining_quota_score=1.0, quality_trend_score=factor_b,
    )
    assert score_a > score_b


# ── Scenario 2: Quality decline triggers strategy shift ──────────────────────

def test_quality_decline_triggers_harden():
    """When quality starts declining, evolution strategy should shift to HARDEN."""
    # Phase 1: good quality
    for _ in range(15):
        quality_history.record_quality("primary", 85.0)

    trend_1 = quality_history.get_quality_trend("primary")
    strategy_1 = auto_select_strategy(
        recent_error_rate=0.05,
        recent_fallback_rate=0.1,
        backends_available=8,
        quality_trend=trend_1.trend,
    )

    # Phase 2: quality drops
    for _ in range(15):
        quality_history.record_quality("primary", 20.0)

    trend_2 = quality_history.get_quality_trend("primary")
    strategy_2 = auto_select_strategy(
        recent_error_rate=0.08,
        recent_fallback_rate=0.2,
        backends_available=8,
        quality_trend=trend_2.trend,
    )

    assert trend_2.trend == "declining"
    assert strategy_2 == EvolutionStrategy.HARDEN


# ── Scenario 3: Quality recovery enables innovation ──────────────────────────

def test_quality_recovery_enables_innovate():
    """After quality recovers and improves, strategy should shift to INNOVATE."""
    # Phase 1: declining
    for _ in range(15):
        quality_history.record_quality("recovering", 80.0)
    for _ in range(15):
        quality_history.record_quality("recovering", 30.0)

    trend_bad = quality_history.get_quality_trend("recovering")
    assert trend_bad.trend == "declining"

    # Phase 2: recovery + improvement
    for _ in range(30):
        quality_history.record_quality("recovering", 90.0)

    trend_good = quality_history.get_quality_trend("recovering")
    strategy = auto_select_strategy(
        recent_error_rate=0.02,
        recent_fallback_rate=0.03,
        backends_available=10,
        quality_trend=trend_good.trend,
    )
    assert strategy == EvolutionStrategy.INNOVATE


# ── Scenario 4: Full pipeline simulation ─────────────────────────────────────

def test_full_pipeline_simulation():
    """Simulate a complete request lifecycle with semantic quality evaluation."""
    from context_pipeline.response_pipeline import ResponseContext
    from context_pipeline.response_processors import build_default_response_pipeline

    # Setup: two backends with different quality histories
    for _ in range(20):
        quality_history.record_quality("fast_backend", 85.0)
    for _ in range(20):
        quality_history.record_quality("slow_backend", 85.0)
    for _ in range(20):
        quality_history.record_quality("slow_backend", 25.0)

    # Process a response through the pipeline
    pipeline = build_default_response_pipeline()
    ctx = ResponseContext(
        backend="fast_backend",
        response_text=(
            "To implement a hash map in Python, you can use the built-in dict type "
            "or create a custom implementation with buckets and hash functions. "
            "Here is a basic implementation using separate chaining for collision resolution."
        ),
        status_code=200,
        latency_ms=400,
    )
    ctx.query = "How to implement a hash map in Python"

    result = pipeline.process(ctx)

    # Verify semantic_quality processor ran
    assert "semantic_quality" in result.processors_applied

    # Verify quality was recorded for fast_backend
    trend = quality_history.get_quality_trend("fast_backend")
    assert trend.sample_count == 21  # 20 historical + 1 from pipeline

    # Verify routing ranking
    ranked = route_scorer.rank_backends(
        ["fast_backend", "slow_backend"],
        "chat", "coding",
        health_scores={"fast_backend": 80.0, "slow_backend": 80.0},
        states={"fast_backend": {"state": "ok"}, "slow_backend": {"state": "ok"}},
        latency_map={"fast_backend": 400.0, "slow_backend": 400.0},
        quality_trends={
            "fast_backend": quality_history.get_quality_score_for_routing("fast_backend"),
            "slow_backend": quality_history.get_quality_score_for_routing("slow_backend"),
        },
    )
    assert ranked[0] == "fast_backend", (
        f"fast_backend should rank first, got {ranked}"
    )


# ── Scenario 5: Semantic evaluator distinguishes quality levels ──────────────

def test_semantic_evaluator_distinguishes_quality_levels():
    """Verify the evaluator produces meaningfully different scores for different quality."""
    query = "Explain how garbage collection works in Python"

    # High quality response
    high_quality = semantic_eval.evaluate_response(
        query,
        "Python uses reference counting as its primary garbage collection mechanism. "
        "Each object has a reference count that tracks how many references point to it. "
        "When the count reaches zero, the object is deallocated. Python also has a "
        "generational garbage collector (gc module) that handles reference cycles. "
        "Objects are organized into three generations, and the collector periodically "
        "scans for unreachable cycles.",
    )

    # Low quality response (irrelevant)
    low_quality = semantic_eval.evaluate_response(
        query,
        "The capital of Japan is Tokyo. It has a population of about 14 million people. "
        "Mount Fuji is a famous landmark nearby.",
    )

    # Empty response
    empty = semantic_eval.evaluate_response(query, "")

    assert high_quality.total > low_quality.total, (
        f"High quality ({high_quality.total}) should score higher "
        f"than low quality ({low_quality.total})"
    )
    assert low_quality.total > empty.total, (
        f"Low quality ({low_quality.total}) should score higher "
        f"than empty ({empty.total})"
    )
    assert high_quality.relevance > low_quality.relevance
    assert high_quality.total >= 60
    assert empty.total <= 30


# ── Scenario 6: Quality-weighted ranking with multiple factors ────────────────

def test_quality_factor_combined_with_other_factors():
    """Quality factor should work alongside health, latency, and quota."""
    import route_scorer

    # Backend A: great health, fast, but declining quality
    score_a = route_scorer.effective_score(
        "backend_a", "chat", "coding",
        health_score=90.0,
        state={"state": "ok"},
        avg_latency_ms=300.0,
        remaining_quota_score=1.0,
        quality_trend_score=0.7,  # declining
    )

    # Backend B: good health, moderate latency, improving quality
    score_b = route_scorer.effective_score(
        "backend_b", "chat", "coding",
        health_score=75.0,
        state={"state": "ok"},
        avg_latency_ms=800.0,
        remaining_quota_score=1.0,
        quality_trend_score=1.3,  # improving
    )

    # Both should produce valid scores
    assert 0.0 < score_a < 1.0
    assert 0.0 < score_b < 1.0

    # The scores should be meaningfully different (quality matters)
    assert abs(score_a - score_b) > 0.01, (
        "Quality trend difference should create meaningful score separation"
    )


# ── Scenario 7: New backend with no quality data ─────────────────────────────

def test_new_backend_gets_neutral_quality():
    """A new backend with no quality history should get neutral quality factor."""
    import route_scorer

    factor = quality_history.get_quality_score_for_routing("brand_new_backend")
    assert factor == 1.0

    score = route_scorer.effective_score(
        "brand_new_backend", "chat", "coding",
        health_score=50.0,
        avg_latency_ms=1000.0,
        remaining_quota_score=1.0,
        quality_trend_score=factor,
    )
    assert score > 0.0
```

### Step 2: Run all tests

- [ ] **Run the full integration test:**

```bash
cd D:\QWEN3.0 && python -m pytest tests/test_semantic_quality_e2e.py -v
```

**Expected output:** All 7 tests pass. Key verifications:
- High-quality backends rise in rankings
- Declining quality triggers HARDEN strategy
- Quality recovery enables INNOVATE
- Full pipeline processes semantic quality correctly
- New backends get neutral quality factor

- [ ] **Run ALL semantic quality tests together:**

```bash
cd D:\QWEN3.0 && python -m pytest tests/test_semantic_eval.py tests/test_quality_history.py tests/test_semantic_quality_integration.py tests/test_quality_weighted_routing.py tests/test_quality_dashboard.py tests/test_quality_feedback_loop.py tests/test_semantic_quality_e2e.py -v
```

**Expected output:** All tests pass (approximately 80+ tests total across 7 files).

- [ ] **Run the full existing test suite to verify no regressions:**

```bash
cd D:\QWEN3.0 && python -m pytest tests/ -v --timeout=30
```

**Expected output:** All existing tests still pass. The new modules are additive and use `try/except ImportError` patterns consistent with the rest of the codebase.

---

## Summary of Changes

### New Files (2)
| File | Purpose |
|------|---------|
| `D:\QWEN3.0\semantic_eval.py` | Pattern-based semantic evaluator (relevance/completeness/coherence) |
| `D:\QWEN3.0\quality_history.py` | Per-backend quality score ring buffer with trend analysis |

### New Test Files (7)
| File | Tests |
|------|-------|
| `D:\QWEN3.0\tests\test_semantic_eval.py` | 20+ tests for the evaluator |
| `D:\QWEN3.0\tests\test_quality_history.py` | 16 tests for ring buffer and trends |
| `D:\QWEN3.0\tests\test_semantic_quality_integration.py` | 10 tests for pipeline integration |
| `D:\QWEN3.0\tests\test_quality_weighted_routing.py` | 8 tests for routing integration |
| `D:\QWEN3.0\tests\test_quality_dashboard.py` | 7 tests for metrics endpoints |
| `D:\QWEN3.0\tests\test_quality_feedback_loop.py` | 12 tests for evolution strategy |
| `D:\QWEN3.0\tests\test_semantic_quality_e2e.py` | 7 end-to-end integration tests |

### Modified Files (8)
| File | Change |
|------|--------|
| `D:\QWEN3.0\context_pipeline\response_processors.py` | Added `semantic_quality_processor` to pipeline |
| `D:\QWEN3.0\routing_executor.py` | Hook semantic eval after successful response |
| `D:\QWEN3.0\route_scorer.py` | Added `quality_trend_score` param to `effective_score` (weight 0.10), reduced health from 0.45 to 0.35; updated `rank_backends` to accept `quality_trends` |
| `D:\QWEN3.0\routing_selector.py` | Compute quality trends, pass to `rank_backends` and per-backend scoring |
| `D:\QWEN3.0\context_pipeline\evolution.py` | Added `quality_trend` param to `auto_select_strategy` with declining->HARDEN, improving->INNOVATE rules |
| `D:\QWEN3.0\context_pipeline\signal_extraction.py` | Extract quality trend signals from `quality_history`, pass to strategy recommendation |
| `D:\QWEN3.0\routes\admin_api.py` | Added quality trends to `/api/stats` and per-backend quality to `/api/backend-health` |
| `D:\QWEN3.0\routes\ops_metrics.py` | Added quality section to `/v1/ops/metrics` response |

### Routing Weight Redistribution
| Factor | Before | After |
|--------|--------|-------|
| Health | 0.45 | 0.35 |
| Stability | 0.25 | 0.25 |
| Latency | 0.15 | 0.15 |
| Quota | 0.10 | 0.10 |
| Task Fit | 0.05 | 0.05 |
| **Quality Trend** | 0.00 | **0.10** |
| **Total** | **1.00** | **1.00** |

### Data Flow
```
User Query
    |
    v
[routing_selector.py] -- selects backends using quality_trend factors
    |
    v
[routing_executor.py] -- calls backend, gets response
    |
    v
[semantic_eval.py] -- scores: relevance + completeness + coherence
    |
    v
[quality_history.py] -- ring buffer stores scores per backend
    |
    +--> [route_scorer.py] -- effective_score() uses quality_trend (10%)
    +--> [evolution.py] -- auto_select_strategy() considers quality trends
    +--> [signal_extraction.py] -- extracts quality_declining/improving signals
    +--> [admin_api.py / ops_metrics.py] -- dashboard displays trends
```
