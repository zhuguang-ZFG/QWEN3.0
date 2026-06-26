"""Lightweight semantic router pre-filter.

P4-2 baseline implementation. Uses keyword/regex rules with calibrated confidence
scores instead of embeddings, avoiding a heavy local model dependency. An
embedding-based backend can be plugged in later by replacing ``_encode_query``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class SemanticRoute:
    """A route recognized by the semantic router."""

    name: str
    intent: str  # maps to routing_intent intent when this route wins
    patterns: list[tuple[re.Pattern[str], float]]
    signals: dict[str, list[str]]
    signal_weights: dict[str, float]


# High-confidence patterns for the most common device / image / think queries.
# Confidence scores are calibrated so only unambiguous queries short-circuit the
# LLM-based intent analyzer.
_ROUTES: tuple[SemanticRoute, ...] = (
    SemanticRoute(
        name="image_gen",
        intent="image_gen",
        patterns=[
            (re.compile(r"画一[个只张幅副]", re.I), 0.95),
            (re.compile(r"画个|画一下|画张", re.I), 0.93),
            (re.compile(r"生成.*图|生成.*图片|generate.*image|create.*image", re.I), 0.92),
            (re.compile(r"帮我画|给我画|draw\s+", re.I), 0.90),
        ],
        signals={
            "action": ["画", "draw", "生成图片", "create image", "generate image"],
            "subject": ["图", "画", "picture", "image"],
        },
        signal_weights={"action": 2.0, "subject": 1.0},
    ),
    SemanticRoute(
        name="device_draw",
        intent="device_draw",
        patterns=[
            (re.compile(r"笔绘|plotter|让机器画|让设备画", re.I), 0.95),
            (re.compile(r"画一只|画一个|画张|画幅.*笔", re.I), 0.90),
        ],
        signals={
            "action": ["笔绘", "plotter", "机器画", "设备画"],
            "subject": ["画", "draw"],
        },
        signal_weights={"action": 2.0, "subject": 1.0},
    ),
    SemanticRoute(
        name="device_write",
        intent="device_write",
        patterns=[
            (re.compile(r"写一行|写个|写字|书写|write\s", re.I), 0.95),
            (re.compile(r"写一句|写首诗|写段话", re.I), 0.92),
        ],
        signals={
            "action": ["写", "write", "书写"],
            "subject": ["字", "诗", "句子"],
        },
        signal_weights={"action": 2.0, "subject": 1.0},
    ),
    SemanticRoute(
        name="device_control",
        intent="device_control",
        patterns=[
            (re.compile(r"回家|home|回原点|归位", re.I), 0.96),
            (re.compile(r"停止|stop|急停|emergency", re.I), 0.96),
            (re.compile(r"设备.*状态|device.*status|在线.*吗", re.I), 0.90),
            (re.compile(r"查.*任务|task.*status|任务.*进度", re.I), 0.90),
        ],
        signals={
            "action": ["回家", "home", "停止", "stop", "急停", "状态", "任务"],
            "target": ["设备", "机器", "笔"],
        },
        signal_weights={"action": 2.0, "target": 1.0},
    ),
    SemanticRoute(
        name="thinking",
        intent="thinking",
        patterns=[
            (re.compile(r"仔细想想|深度分析|深入分析|深度思考", re.I), 0.93),
            (re.compile(r"逐步推理|一步一步|分步骤|详细推导|严格证明", re.I), 0.93),
            (re.compile(r"think carefully|think step by step|step by step", re.I), 0.92),
            (re.compile(r"prove that|formal proof|mathematical proof", re.I), 0.92),
        ],
        signals={
            "trigger": ["仔细", "深入", "逐步", "step by step", "prove", "证明"],
            "context": ["分析", "推理", "推导"],
        },
        signal_weights={"trigger": 2.0, "context": 1.0},
    ),
    SemanticRoute(
        name="code_generation",
        intent="code_generation",
        patterns=[
            (re.compile(r"写.*代码|生成.*代码|实现.*函数|代码示例", re.I), 0.93),
            (re.compile(r"用\s*(python|js|javascript|typescript|rust|go|c\+\+)\s*写.*", re.I), 0.96),
        ],
        signals={
            "action": ["写代码", "生成代码", "实现", "代码示例"],
            "lang": ["python", "javascript", "typescript", "rust", "go"],
        },
        signal_weights={"action": 2.0, "lang": 1.5},
    ),
)


def _pattern_score(query: str, route: SemanticRoute) -> float:
    """Return the highest confidence of any matching pattern."""
    return max((conf for pat, conf in route.patterns if pat.search(query)), default=0.0)


def _signal_score(query: str, route: SemanticRoute) -> float:
    """Return a normalized weighted score based on keyword signals.

    Signals are capped at 0.80 so only unambiguous regex patterns can reach the
    default 0.85 short-circuit threshold. This prevents single-keyword queries
    like "画" from incorrectly hijacking the intent analyzer.
    """
    text = query.lower()
    total_weight = sum(route.signal_weights.values())
    if total_weight == 0:
        return 0.0
    score = 0.0
    for bucket, words in route.signals.items():
        weight = route.signal_weights.get(bucket, 1.0)
        if any(word.lower() in text for word in words):
            score += weight
    return min(0.80, score / total_weight)


def _encode_query(
    query: str,
    *,
    encoder: Callable[[str], list[float]] | None = None,
) -> list[float] | None:
    """Placeholder for future embedding backend. Returns None to use rule scores."""
    if encoder is None:
        return None
    return encoder(query)


def classify(
    query: str,
    *,
    threshold: float = 0.85,
    encoder: Callable[[str], list[float]] | None = None,
) -> tuple[str, str, float] | None:
    """Return (route_name, intent, confidence) when confidence >= threshold.

    The default rule-based backend requires no external dependencies. Pass an
    ``encoder`` returning normalized embeddings to switch to cosine-similarity
    scoring against pre-computed route embeddings.
    """
    if not query or not query.strip():
        return None
    text = query.strip()

    emb = _encode_query(text, encoder=encoder)
    if emb is not None:
        return _classify_by_embedding(text, emb, threshold)

    best: tuple[str, str, float] | None = None
    for route in _ROUTES:
        score = max(_pattern_score(text, route), _signal_score(text, route))
        if score >= threshold and (best is None or score > best[2]):
            best = (route.name, route.intent, score)
    return best


def _classify_by_embedding(
    query: str,
    query_emb: list[float],
    threshold: float,
) -> tuple[str, str, float] | None:
    """Cosine-similarity classifier using pre-computed route embeddings.

    This is a stub: route embeddings would be pre-computed at import time once
    an encoder is supplied. For now it always returns None so the rule backend
    remains the default.
    """
    del query, query_emb, threshold
    return None
