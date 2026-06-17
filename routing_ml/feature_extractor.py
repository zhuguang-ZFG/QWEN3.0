"""Extract feature vectors from routing requests for ML prediction.

12-dimensional feature vector (pure Python, zero dependencies):
  0: message_length (normalized, 0-1)
  1: code_block_ratio (fraction of content in ``` fences)
  2: file_reference_count (normalized)
  3: has_debug_keyword (0 or 1)
  4: chinese_ratio (fraction of non-ASCII chars)
  5-9: top5_backend_health (1=healthy, 0.5=degraded, 0=dead)
  10-11: scenario_onehot (coding=10, chat=01, other=00)
"""

from __future__ import annotations

import re
from dataclasses import dataclass

N_FEATURES = 12

_DEBUG_KEYWORDS = frozenset(
    {
        "debug",
        "fix",
        "error",
        "bug",
        "crash",
        "exception",
        "traceback",
        "stack trace",
        "panic",
        "segfault",
        "修复",
        "报错",
        "异常",
        "崩溃",
        "调试",
        "出错",
    }
)

_CODE_FENCE_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)
_FILE_REF_RE = re.compile(r"(?:^|\s)([\w/\\.-]+\.(?:py|js|ts|tsx|jsx|go|rs|java|c|cpp|rb|php))\b")
_CHINESE_RE = re.compile(r"[一-鿿㐀-䶿]")


@dataclass
class FeatureVector:
    features: list[float]  # length N_FEATURES
    metadata: dict  # human-readable feature names


def extract_features(
    messages: list[dict],
    scenario: str = "",
    health_map: dict | None = None,
    top_backends: list[str] | None = None,
) -> FeatureVector:
    """Extract a 12-dim feature vector from a request."""
    text = _concat_messages(messages)
    total_len = max(len(text), 1)

    msg_len = min(total_len / 10000.0, 1.0)

    code_fences = _CODE_FENCE_RE.findall(text)
    code_chars = sum(len(f) for f in code_fences)
    code_ratio = min(code_chars / max(total_len, 1), 1.0)

    file_refs = _FILE_REF_RE.findall(text)
    file_count = min(len(file_refs) / 10.0, 1.0)

    has_debug = 1.0 if any(kw in text.lower() for kw in _DEBUG_KEYWORDS) else 0.0

    chinese_chars = len(_CHINESE_RE.findall(text))
    chinese_ratio = min(chinese_chars / max(total_len, 1), 1.0)

    top5 = (top_backends or [])[:5]
    health_arr = [0.0] * 5
    if health_map:
        for i, b in enumerate(top5):
            h = health_map.get(b, "healthy")
            health_arr[i] = {"healthy": 1.0, "degraded": 0.5, "dead": 0.0}.get(h, 0.5)

    scenario_arr = [0.0, 0.0]
    if scenario == "coding":
        scenario_arr[0] = 1.0
    elif scenario == "chat":
        scenario_arr[1] = 1.0

    features = [msg_len, code_ratio, file_count, has_debug, chinese_ratio] + health_arr + scenario_arr

    metadata = {
        "message_length": round(msg_len, 3),
        "code_block_ratio": round(code_ratio, 3),
        "file_reference_count": round(file_count, 3),
        "has_debug_keyword": has_debug,
        "chinese_ratio": round(chinese_ratio, 3),
        "top5_health": {top5[i]: health_arr[i] for i in range(len(top5))},
        "scenario": scenario,
    }

    return FeatureVector(features=features, metadata=metadata)


def _concat_messages(messages: list[dict]) -> str:
    parts = []
    for m in messages:
        if isinstance(m, dict):
            parts.append(str(m.get("content", "")))
        else:
            parts.append(str(getattr(m, "content", "")))
    return "\n".join(parts)
