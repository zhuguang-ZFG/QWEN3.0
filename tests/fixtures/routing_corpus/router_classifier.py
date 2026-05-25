"""Fixture stub: rule and signal classifiers for intent routing."""

import re

RULES = [
    (r"写.*代码|implement function", "code_generation", 0.9),
    (r"架构|design pattern", "architecture", 0.85),
]


def rule_classify(query: str):
    for pattern, intent, confidence in RULES:
        if re.search(pattern, query, re.IGNORECASE):
            return {"intent": intent, "confidence": confidence, "source": "rules"}
    return None


def signal_classify(query: str):
    if "python" in query.lower() and "sort" in query.lower():
        return {"intent": "code_generation", "confidence": 0.8, "source": "signal_v2"}
    return None


def analyze(query: str, system_prompt: str = "", ide: str = "unknown"):
    return rule_classify(query) or signal_classify(query) or {
        "intent": "unknown",
        "confidence": 0.5,
        "source": "default_fallback",
    }
