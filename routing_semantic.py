"""意图语义分类器 — 基于 n-gram TF-IDF 余弦相似度。

纯 Python 实现，零外部依赖，毫秒级决策。在正则规则和信号分类器均未命中时，
提供基于语义相似度的后备分类，减少对 LLM 后备的依赖。

参考 Semantic Router 的 RouteLayer + Encoder 抽象，但用 n-gram TF-IDF
替代神经嵌入，避免引入 sentence-transformers 或网络 API 调用。
"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from typing import Any

logger = logging.getLogger(__name__)

# 意图 → 示例句（每意图 4-6 个，覆盖中英文常见表达）
_EXAMPLES: dict[str, list[str]] = {
    "device_draw": [
        "画一只猫",
        "帮我画个简笔画",
        "让绘图机画一个圆",
        "draw a picture",
        "生成一张线条画",
        "画个爱心",
    ],
    "device_write": [
        "写一行你好",
        "写字",
        "帮我写首诗",
        "write hello world",
        "书写文字",
        "写个名字",
    ],
    "device_control": [
        "回家",
        "停止",
        "急停",
        "回原点",
        "go home",
        "stop machine",
        "emergency stop",
    ],
    "code_generation": [
        "写一个函数",
        "生成代码",
        "帮我实现一个排序算法",
        "write a function",
        "implement a class",
        "写个脚本",
    ],
    "debugging": [
        "这个报错什么意思",
        "帮我修复bug",
        "为什么报错",
        "fix this error",
        "debug this crash",
        "程序崩溃了",
    ],
    "explanation": [
        "什么是PID控制",
        "解释一下FOC",
        "原理是什么",
        "explain how this works",
        "what is the difference",
        "帮我理解",
    ],
    "trivial": [
        "你好",
        "hello",
        "hi",
        "谢谢",
        "再见",
        "在吗",
    ],
    "image_gen": [
        "画一张图",
        "生成图片",
        "AI画图",
        "generate image",
        "create a picture",
        "帮我画张图",
    ],
    "chat": [
        "今天天气怎么样",
        "讲个笑话",
        "推荐一本书",
        "how are you",
        "tell me a story",
        "聊聊天",
    ],
}


def _ngrams(text: str, n: int = 2) -> Counter[str]:
    """提取字符 n-gram（支持中英文混合）。"""
    text = text.lower().strip()
    tokens = re.findall(r"[\w\u4e00-\u9fff]+", text)
    counter: Counter[str] = Counter()
    for token in tokens:
        if len(token) < n:
            counter[token] += 1
        else:
            for i in range(len(token) - n + 1):
                counter[token[i : i + n]] += 1
    return counter


def _tfidf(counter: Counter[str], idf: dict[str, float]) -> dict[str, float]:
    """TF-IDF 向量化。"""
    total = sum(counter.values())
    if total == 0:
        return {}
    return {ng: (cnt / total) * idf.get(ng, 1.0) for ng, cnt in counter.items()}


def _cosine(v1: dict[str, float], v2: dict[str, float]) -> float:
    """稀疏向量余弦相似度。"""
    if not v1 or not v2:
        return 0.0
    dot = sum(v1[k] * v2[k] for k in v1.keys() & v2.keys())
    n1 = math.sqrt(sum(v * v for v in v1.values()))
    n2 = math.sqrt(sum(v * v for v in v2.values()))
    if n1 == 0 or n2 == 0:
        return 0.0
    return dot / (n1 * n2)


class SemanticClassifier:
    """意图语义分类器（n-gram TF-IDF 余弦相似度）。"""

    def __init__(self) -> None:
        self._idf: dict[str, float] = {}
        self._vectors: dict[str, list[dict[str, float]]] = {}
        self._ready = False

    def _init(self) -> None:
        """惰性初始化：计算 IDF 和示例向量。"""
        if self._ready:
            return
        docs: list[str] = []
        for examples in _EXAMPLES.values():
            docs.extend(examples)
        n_docs = len(docs)
        df: Counter[str] = Counter()
        for doc in docs:
            for ng in _ngrams(doc):
                df[ng] += 1
        self._idf = {ng: math.log(n_docs / (1 + freq)) for ng, freq in df.items()}
        for intent, examples in _EXAMPLES.items():
            self._vectors[intent] = [_tfidf(_ngrams(ex), self._idf) for ex in examples]
        self._ready = True

    def classify(self, query: str, *, threshold: float = 0.3) -> dict[str, Any] | None:
        """语义分类，返回 top-1 意图 + 置信度。

        Args:
            query: 用户查询文本。
            threshold: 最低余弦相似度阈值，低于此值返回 None。

        Returns:
            分类结果 dict（与 _rule_classify 格式对齐）或 None。
        """
        self._init()
        query_vec = _tfidf(_ngrams(query), self._idf)
        if not query_vec:
            return None

        best_intent: str | None = None
        best_sim = 0.0
        for intent, vectors in self._vectors.items():
            for vec in vectors:
                sim = _cosine(query_vec, vec)
                if sim > best_sim:
                    best_sim = sim
                    best_intent = intent

        if best_intent is None or best_sim < threshold:
            return None

        return {
            "intent": best_intent,
            "complexity": 0.7 if best_intent == "code_generation" else 0.3,
            "needs_code": best_intent in ("code_generation", "debugging"),
            "domain_keywords": [],
            "cnc_subdomain": "general",
            "source": "semantic_tfidf",
            "confidence": min(best_sim, 0.90),
        }


_classifier: SemanticClassifier | None = None


def semantic_classify(query: str) -> dict[str, Any] | None:
    """模块级便捷接口（单例惰性初始化）。"""
    global _classifier
    if _classifier is None:
        _classifier = SemanticClassifier()
    return _classifier.classify(query)
