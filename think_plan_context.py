"""Think-Plan-Context layer — multi-step reasoning + project awareness.

Enhances vibecode with:
  1. Think: structured reasoning before coding (chain-of-thought prompt)
  2. Plan: task decomposition for complex requests
  3. Context: auto-discover project structure and relevant files
"""

from __future__ import annotations

import logging
import os
import re
from collections import defaultdict
from pathlib import Path

_log = logging.getLogger(__name__)

# Steps threshold: longer/complex prompts get plan→execute→verify
_PLAN_THRESHOLD_CHARS = 200
_PLAN_SIGNALS = [
    "implement", "build", "create", "refactor", "重构",
    "实现", "构建", "创建", "multi-file", "多文件", "module",
    "fix all", "修复所有", "add feature", "添加功能",
    "api", "endpoint", "database", "migration",
]

_THINKING_PROMPT = (
    "Before writing code, think step by step:\n"
    "1. Understand the goal and constraints\n"
    "2. Identify ALL affected files and dependencies\n"
    "3. Choose the simplest approach that works\n"
    "4. Consider edge cases and error handling\n"
    "5. Edit ALL affected files in ONE response (parallel edits are faster)\n\n"
    "Then implement with clear, tested code."
)


def needs_plan(query: str) -> bool:
    """Determine if a query is complex enough to benefit from plan→execute."""
    if len(query) > _PLAN_THRESHOLD_CHARS:
        return True
    q = query.lower()
    return any(s in q for s in _PLAN_SIGNALS)


def build_think_prompt(query: str, context: str = "") -> str:
    """Build an enhanced system prompt with thinking + context."""
    parts = [_THINKING_PROMPT]
    if context:
        parts.insert(0, context)
    return "\n\n".join(parts)


def build_plan_prompt(query: str, files: list[str]) -> str:
    """Generate a plan-first prompt that asks the model to plan before coding."""
    file_list = "\n".join(f"  - {f}" for f in files[:10])
    return (
        f"Task: {query}\n\n"
        f"Project files:\n{file_list}\n\n"
        "First, write a brief plan (3-5 steps). Then implement each step. "
        "After implementation, verify by running appropriate tests or checks."
    )


# ── Project Context Discovery ─────────────────────────────────────────────────

_SCAN_IGNORE = {
    "venv", "node_modules", "__pycache__", ".git", ".codegraph",
    "dist", "build", "egg-info", "esp32S_XYZ", "PyWxDump",
    "mempalace", "codegraph", "wx_key_tool", "lima-miniprogram",
}


def discover_project_files(
    root: str | None = None, max_files: int = 80,
) -> dict[str, list[str]]:
    """Walk project and group source files by directory.

    Distributes budget across directories to avoid root dir hogging all slots.
    """
    root = root or os.getcwd()
    root_path = Path(root).resolve()
    by_dir: dict[str, list[str]] = defaultdict(list)
    _per_dir_limit = 80  # Cap per directory to ensure breadth

    for entry in sorted(root_path.rglob("*"), key=lambda p: (len(p.parts), str(p))):
        if any(p in _SCAN_IGNORE for p in entry.parts):
            continue
        if entry.is_file() and entry.suffix in (
            ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs",
        ):
            rel = str(entry.relative_to(root_path))
            directory = str(entry.parent.relative_to(root_path)) or "."
            if len(by_dir[directory]) < _per_dir_limit:
                by_dir[directory].append(rel)
                if sum(len(v) for v in by_dir.values()) >= max_files:
                    return dict(by_dir)

    return dict(by_dir)


def find_related_files(
    query: str, project_files: dict[str, list[str]], max_files: int = 5,
) -> list[str]:
    """Find files related to a coding query by matching keywords."""
    keywords = _extract_keywords(query)
    scored: list[tuple[str, float]] = []

    for directory, files in project_files.items():
        dir_lower = directory.lower()
        for f in files:
            f_lower = f.lower()
            score = sum(
                1 for kw in keywords
                if kw.lower() in f_lower or kw.lower() in dir_lower
            )
            if score > 0:
                scored.append((f, score))

    scored.sort(key=lambda x: -x[1])
    return [f for f, _ in scored[:max_files]]


def _extract_keywords(query: str) -> list[str]:
    """Extract meaningful keywords from a query."""
    keywords: list[str] = []
    # File mentions (highest priority)
    keywords.extend(re.findall(r"[\w/\\.-]+\.\w{2,4}", query))
    # CapitalizedWords (likely class/module names)
    keywords.extend(re.findall(r"\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b", query))
    # snake_case identifiers
    keywords.extend(re.findall(r"\b([a-z]+_[a-z]+(?:_[a-z]+)*)\b", query))
    # Tech terms
    tech_terms = re.findall(
        r"\b(api|router|handler|model|store|config|"
        r"auth|login|user|admin|test|util|helper|"
        r"server|client|cache|queue|worker|task|"
        r"engine|stream|async|routing|proxy|backend|"
        r"tool|forward|bridge|selector|executor|"
        r"registry|gateway|session|memory|orchestrat)\b",
        query, re.I,
    )
    keywords.extend(tech_terms)
    # Any word >4 chars that isn't a stopword
    stopwords = {"this", "that", "with", "from", "have", "been", "were",
                 "when", "will", "would", "could", "should", "about",
                 "into", "over", "after", "before", "between"}
    words = re.findall(r"\b([a-z]{4,20})\b", query.lower())
    keywords.extend(w for w in words if w not in stopwords)
    return list(dict.fromkeys(keywords))[:15]


def build_context_summary(
    query: str, project_root: str | None = None, max_files: int = 8,
) -> str:
    """Build a project context summary for injection into coding prompts."""
    project_files = discover_project_files(project_root)

    if not project_files:
        return ""

    related = find_related_files(query, project_files, max_files)

    if not related:
        return ""

    lines = ["[Project Context — auto-detected]"]
    for f in related[:max_files]:
        lines.append(f"  {f}")
    lines.append(f"\n  ({len(project_files)} dirs, "
                 f"{sum(len(v) for v in project_files.values())} src files total)")

    return "\n".join(lines)


def enhance_coding_prompt(query: str, messages: list[dict] | None = None) -> dict:
    """Main entry: enhance a coding request with thinking + planning + context.

    Returns dict with:
      - enhanced_query: modified user prompt with plan instructions
      - system_prompt: thinking prompt with project context
      - context_files: list of related file paths
    """
    project_root = os.environ.get("LIMA_PROJECT_ROOT", os.getcwd())
    context = build_context_summary(query, project_root)
    context_files = find_related_files(
        query, discover_project_files(project_root),
    )

    if needs_plan(query):
        system = build_think_prompt(query, context)
        enhanced = build_plan_prompt(query, context_files)
    else:
        system = _THINKING_PROMPT if context else ""
        enhanced = query

    return {
        "enhanced_query": enhanced if enhanced != query else query,
        "system_prompt": system,
        "context_files": context_files,
        "needs_plan": needs_plan(query),
    }
