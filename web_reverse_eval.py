"""Safe admission helpers for web-reverse and local-proxy model batches."""

from __future__ import annotations

import json
import re
import statistics
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from coding_eval import CodingCase, EvalResult


WEB_REVERSE_NAME_PATTERNS = (
    "ddg_",
    "longcat_web",
    "mimo_web",
    "oldllm_",
    "scnet_large",
)

AUTH_OR_QUOTA_MARKERS = (
    "anonymous",
    "auth",
    "captcha",
    "cookie",
    "login",
    "manual refresh",
    "quota",
    "rate limit",
    "rate_limited",
    "usage_exceeded",
)


def load_inventory(path: str | Path) -> list[dict]:
    inventory_path = Path(path)
    if not inventory_path.exists():
        return []
    data = json.loads(inventory_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"inventory must be a list: {inventory_path}")
    return data


def discover_web_reverse_backends(
    inventory: Iterable[dict], backends: dict[str, dict]
) -> list[str]:
    """Return registered web-reverse backends without inventing missing names."""
    selected: list[str] = []
    seen: set[str] = set()

    for item in inventory:
        for name in item.get("lima_backends", []) or []:
            if name in backends and name not in seen:
                selected.append(name)
                seen.add(name)

    for name, cfg in sorted(backends.items()):
        if name in seen:
            continue
        if _looks_like_web_reverse_backend(name, cfg):
            selected.append(name)
            seen.add(name)

    return selected


def safe_web_reverse_cases() -> list[CodingCase]:
    """Synthetic public fixtures only; no repository snippets or local paths."""
    return [
        CodingCase(
            id="public_python_bugfix",
            name="Fix public Python indexing bug",
            prompt=(
                "Fix this Python function. Return only the corrected function in a "
                "Python code block.\n\n```python\n"
                "def last_item(items):\n"
                "    return items[len(items)]\n"
                "```"
            ),
            required_patterns=["def last_item", r"items\[-1\]|items\[len\(items\) - 1\]"],
            forbidden_patterns=["I cannot", "as an AI", "IndexError"],
            min_chars=35,
            max_tokens=256,
            python_must_compile=True,
            tags=["python", "bugfix", "safe-web-reverse"],
        ),
        CodingCase(
            id="public_code_review",
            name="Review public average function",
            prompt=(
                "Review this function and identify the most important bug. Be "
                "concise and do not rewrite unrelated code.\n\n```python\n"
                "def average(nums):\n"
                "    total = 0\n"
                "    for n in nums:\n"
                "        total += n\n"
                "    return total / len(nums)\n"
                "```"
            ),
            required_patterns=[r"empty|zero|len\(nums\)|division"],
            forbidden_patterns=["complete rewrite", "payment", "billing"],
            min_chars=40,
            max_tokens=256,
            tags=["review", "python", "safe-web-reverse"],
        ),
        CodingCase(
            id="public_json_plan",
            name="Return strict JSON plan",
            prompt=(
                "Return only a JSON object with keys action, files, and reason. "
                "The task is: update a generic app router to prefer coding-capable "
                "models for editor requests. No markdown, no prose."
            ),
            required_patterns=[r'"action"', r'"files"', r'"reason"'],
            forbidden_patterns=["```", "Here is", "I would"],
            required_json_keys=["action", "files", "reason"],
            min_chars=30,
            max_tokens=256,
            tags=["json", "tool", "safe-web-reverse"],
        ),
    ]


def summarize_results(results: Iterable[EvalResult]) -> dict[str, dict]:
    grouped: dict[str, list[EvalResult]] = {}
    for result in results:
        grouped.setdefault(result.backend, []).append(result)

    summaries: dict[str, dict] = {}
    for backend, rows in sorted(grouped.items()):
        avg_score = int(statistics.mean(row.score for row in rows))
        avg_latency = int(statistics.mean(row.latency_ms for row in rows))
        passes = sum(1 for row in rows if row.ok)
        summaries[backend] = {
            "backend": backend,
            "cases": len(rows),
            "passes": passes,
            "avg_score": avg_score,
            "avg_latency_ms": avg_latency,
            "recommendation": _recommend(rows, passes, avg_score, avg_latency),
            "notes": _collect_notes(rows),
        }
    return summaries


def cap_backend_timeouts(
    backends: dict[str, dict], selected: Iterable[str], cap_seconds: int
) -> int:
    if cap_seconds <= 0:
        return 0
    changed = 0
    for name in selected:
        cfg = backends.get(name)
        if not cfg:
            continue
        current = int(cfg.get("timeout", cap_seconds))
        if current > cap_seconds:
            cfg["timeout"] = cap_seconds
            changed += 1
    return changed


def write_json_report(
    results: Iterable[EvalResult], summaries: dict[str, dict], path: str | Path
) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_by": "scripts/eval_web_reverse_models.py",
        "safety": {
            "private_code_allowed": False,
            "promotes_routes_automatically": False,
            "prompt_set": "synthetic_public_only",
        },
        "summaries": list(summaries.values()),
        "results": [asdict(result) for result in results],
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_markdown_report(
    results: Iterable[EvalResult], summaries: dict[str, dict], path: str | Path
) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    result_rows = list(results)
    lines = [
        "# Web Reverse Model Eval",
        "",
        "> Generated by `scripts/eval_web_reverse_models.py`.",
        "> Prompts are synthetic/public only; this report does not promote routes automatically.",
        "",
        "| Backend | Recommendation | Avg Score | Passes | Avg Latency | Notes |",
        "|---|---|---:|---:|---:|---|",
    ]
    for summary in summaries.values():
        notes = "; ".join(summary["notes"]) or "ok"
        lines.append(
            "| `{backend}` | `{recommendation}` | {avg_score} | {passes}/{cases} | "
            "{avg_latency_ms}ms | {notes} |".format(
                notes=notes,
                backend=summary["backend"],
                recommendation=summary["recommendation"],
                avg_score=summary["avg_score"],
                passes=summary["passes"],
                cases=summary["cases"],
                avg_latency_ms=summary["avg_latency_ms"],
            )
        )
    lines.extend(["", "## Case Results", ""])
    lines.extend(["| Backend | Case | Score | Latency | Notes |", "|---|---|---:|---:|---|"])
    for row in result_rows:
        lines.append(
            f"| `{row.backend}` | `{row.case_id}` | {row.score} | "
            f"{row.latency_ms}ms | {'; '.join(row.notes) or 'ok'} |"
        )
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _looks_like_web_reverse_backend(name: str, cfg: dict) -> bool:
    lowered_name = name.lower()
    if lowered_name == "kimi" or lowered_name.startswith("kimi_"):
        return True
    if any(pattern in lowered_name for pattern in WEB_REVERSE_NAME_PATTERNS):
        return True
    url = str(cfg.get("url", "")).lower()
    return bool(re.search(r"https?://(?:localhost|127\.0\.0\.1):45\d{2}/", url))


def _recommend(
    rows: list[EvalResult], passes: int, avg_score: int, avg_latency_ms: int
) -> str:
    if passes == 0 and _has_auth_or_quota_failure(rows):
        return "disabled_auth_or_quota"
    if len(rows) < 3:
        if passes == len(rows):
            return "phase2_required"
        if passes >= 1:
            return "sandbox_only"
        return "disabled_provider_error"
    if passes == len(rows) and avg_score >= 85 and avg_latency_ms <= 45_000:
        return "code_medium_candidate"
    if passes >= 2 and avg_latency_ms <= 60_000:
        return "code_floor_candidate"
    if passes >= 1:
        return "sandbox_only"
    return "disabled_provider_error"


def _has_auth_or_quota_failure(rows: list[EvalResult]) -> bool:
    combined = " ".join(" ".join(row.notes).lower() for row in rows)
    return any(marker in combined for marker in AUTH_OR_QUOTA_MARKERS)


def _collect_notes(rows: list[EvalResult]) -> list[str]:
    notes: list[str] = []
    for row in rows:
        for note in row.notes[:2]:
            entry = f"{row.case_id}: {note}"
            if entry not in notes:
                notes.append(entry)
    return notes[:6]
