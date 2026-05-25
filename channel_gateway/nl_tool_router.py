"""Map natural Chinese phrases to slash tool commands."""

from __future__ import annotations

import re

# (pattern, repl) — repl may use \1 groups
_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^(.{1,24})的天气$"), r"/天气 \1"),
    (re.compile(r"^天气\s*(.+)$"), r"/天气 \1"),
    (re.compile(r"^查一下(.{1,24})天气$"), r"/天气 \1"),
    (re.compile(r"^算一下\s*(.+)$"), r"/算 \1"),
    (re.compile(r"^算算\s*(.+)$"), r"/算 \1"),
    (re.compile(r"^计算\s*(.+)$"), r"/算 \1"),
    (re.compile(r"^搜一下\s*(.+)$"), r"/搜 \1"),
    (re.compile(r"^搜索\s*(.+)$"), r"/搜 \1"),
    (re.compile(r"^翻译\s*(.+)$"), r"/翻译 \1"),
    (re.compile(r"^百科\s*(.+)$"), r"/百科 \1"),
    (re.compile(r"^查百科\s*(.+)$"), r"/百科 \1"),
    (re.compile(r"^股票\s*(.+)$"), r"/股票 \1"),
    (re.compile(r"^查股票\s*(.+)$"), r"/股票 \1"),
    (re.compile(r"^汇率\s*(.+)$"), r"/汇率 \1"),
    (re.compile(r"^热搜\s*(.*)$"), r"/热搜 \1"),
    (re.compile(r"^现在几点了?$"), r"/时间"),
    (re.compile(r"^几点了?$"), r"/时间"),
    (re.compile(r"^地震$"), r"/地震"),
    (re.compile(r"^黄历$"), r"/黄历"),
]


def match_nl_tool(text: str) -> str | None:
    raw = (text or "").strip()
    if not raw or raw.startswith("/"):
        return None
    compact = re.sub(r"[\s!！?？。.~、，,]+$", "", raw)
    for pat, repl in _RULES:
        if pat.match(compact):
            if "\\1" in repl:
                return pat.sub(repl, compact)
            return repl
    return None
