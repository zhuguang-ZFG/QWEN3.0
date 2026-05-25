"""Exact-output and direct-answer heuristics for routes/quality_gate."""

from __future__ import annotations

EXACT_OUTPUT_MARKERS = (
    "return exactly",
    "respond exactly",
    "output exactly",
    "print exactly",
    "exactly:",
    "only return",
    "only output",
    "\u53ea\u8fd4\u56de",
    "\u53ea\u8f93\u51fa",
    "\u4ec5\u8fd4\u56de",
    "\u4ec5\u8f93\u51fa",
)


def allows_short_direct_answer(query: str, response_text: str) -> bool:
    if not query or not response_text:
        return False
    lowered = query.lower()
    if not any(marker in lowered for marker in EXACT_OUTPUT_MARKERS):
        return False
    return 1 <= len(response_text.strip()) <= 120


def _strip_direct_answer(value: str) -> str:
    return value.strip().strip("\"'`\u201c\u201d\u2018\u2019")


def expected_direct_answer(query: str) -> str:
    if not query:
        return ""
    lowered = query.lower()
    for marker in (
        "return exactly",
        "respond exactly",
        "output exactly",
        "print exactly",
        "only return",
        "only output",
    ):
        idx = lowered.rfind(marker)
        if idx < 0:
            continue
        rest = query[idx + len(marker):].strip()
        if not rest or rest[0] not in (":", "\uff1a"):
            continue
        candidate = _strip_direct_answer(rest[1:])
        if candidate and "\n" not in candidate and len(candidate) <= 120:
            return candidate
    for marker in (
        "\u53ea\u8fd4\u56de",
        "\u53ea\u8f93\u51fa",
        "\u4ec5\u8fd4\u56de",
        "\u4ec5\u8f93\u51fa",
    ):
        idx = query.rfind(marker)
        if idx < 0:
            continue
        rest = query[idx + len(marker):].strip()
        if rest.startswith((":", "\uff1a")):
            rest = rest[1:].strip()
        candidate = _strip_direct_answer(rest)
        if candidate and "\n" not in candidate and len(candidate) <= 120:
            return candidate
    return ""
