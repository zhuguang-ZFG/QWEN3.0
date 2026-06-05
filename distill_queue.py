"""Distill queue — extracted from smart_router.py (Slice 3).

Logs Q&A pairs with quality scoring for routing feedback.
Migrated from smart_router.py L155–228.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from datetime import datetime

DEBUG = os.environ.get("LIMA_DEBUG", "") == "1"
DISTILL_QUEUE_DIR = os.path.join(os.path.dirname(__file__), "data", "distill_queue", "pending")


def _quick_score(query: str, answer: str) -> float:
    if not answer:
        return 0.0

    length = len(answer)
    if 100 <= length <= 2000:
        len_score = 1.0
    elif length < 50:
        len_score = 0.0
    elif length < 100:
        len_score = (length - 50) / 50
    else:
        len_score = max(0.7, 1.0 - (length - 2000) / 5000)

    fmt_score = 0.0
    if "```" in answer and answer.count("```") % 2 == 0:
        fmt_score += 0.4
    if any(char.isdigit() for char in answer):
        fmt_score += 0.3
    if any(marker in answer for marker in ["1.", "2.", "- ", "* ", "步骤"]):
        fmt_score += 0.3

    comp_score = 1.0
    if any(marker in answer for marker in ["抱歉", "无法", "不确定", "我不能", "暂时不可用"]):
        comp_score = 0.3

    query_words = set(query.lower().replace("?", "").replace("？", "").split())
    answer_lower = answer.lower()
    if query_words:
        overlap = sum(1 for word in query_words if word in answer_lower and len(word) > 1)
        rel_score = min(1.0, overlap / max(len(query_words) * 0.3, 1))
    else:
        rel_score = 0.5

    return round(len_score * 0.3 + fmt_score * 0.3 + comp_score * 0.2 + rel_score * 0.2, 3)


def log_to_distill_queue(query: str, answer: str, intent: dict, backend: str) -> None:
    if os.environ.get("DISTILL_LOG", "0") != "1":
        return
    if backend == "local":
        return
    if not answer or "暂时不可用" in answer:
        return

    try:
        os.makedirs(DISTILL_QUEUE_DIR, exist_ok=True)
        score = _quick_score(query, answer)
        entry = {
            "query": query,
            "answer": answer,
            "intent": intent.get("intent", "unknown"),
            "complexity": intent.get("complexity", 0.5),
            "source_backend": backend,
            "quality_score": score,
            "routing_correct": score >= 0.7,
            "logged_at": datetime.now().isoformat(),
        }
        qhash = hashlib.md5(query.encode()).hexdigest()[:8]
        ts = time.strftime("%Y%m%d_%H%M%S")
        fname = os.path.join(DISTILL_QUEUE_DIR, f"{ts}_{qhash}.json")
        with open(fname, "w", encoding="utf-8") as handle:
            json.dump(entry, handle, ensure_ascii=False, indent=2)
        if DEBUG:
            print(f"[DISTILL] logged: {query[:30]}... -> {backend}", file=sys.stderr)
    except Exception as exc:
        if DEBUG:
            print(f"[DISTILL] log failed: {exc}", file=sys.stderr)
