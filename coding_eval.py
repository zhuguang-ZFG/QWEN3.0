"""Small coding-backend evaluation utilities for the personal LiMa assistant."""

from __future__ import annotations

import argparse
import json
import re
import statistics
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable


CODE_SIGNALS = (
    "coder",
    "codestral",
    "code",
    "qwen",
    "deepseek",
    "gpt",
    "claude",
    "kimi",
    "swe",
    "devstral",
    "mistral",
)


@dataclass(frozen=True)
class CodingCase:
    id: str
    name: str
    prompt: str
    required_patterns: list[str] = field(default_factory=list)
    forbidden_patterns: list[str] = field(default_factory=list)
    required_json_keys: list[str] = field(default_factory=list)
    min_chars: int = 20
    max_chars: int = 0
    max_tokens: int = 512
    python_must_compile: bool = False
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EvalResult:
    backend: str
    case_id: str
    score: int
    latency_ms: int
    ok: bool
    notes: list[str]
    response_preview: str


def load_cases(case_dir: str | Path) -> list[CodingCase]:
    root = Path(case_dir)
    cases: list[CodingCase] = []
    paths = [root] if root.is_file() else sorted(root.glob("*.json"))
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            cases.extend(CodingCase(**item) for item in data)
        else:
            cases.append(CodingCase(**data))
    if not cases:
        raise ValueError(f"no coding cases found in {root}")
    return cases


def candidate_backends(
    backends: dict[str, dict], *, include_unconfigured: bool = False
) -> list[str]:
    candidates: list[str] = []
    for name, cfg in sorted(backends.items()):
        key = str(cfg.get("key", ""))
        if not include_unconfigured and not key:
            continue
        haystack = " ".join(
            [
                name,
                str(cfg.get("model", "")),
                str(cfg.get("url", "")),
                " ".join(cfg.get("caps", [])) if isinstance(cfg.get("caps"), list) else "",
            ]
        ).lower()
        if any(signal in haystack for signal in CODE_SIGNALS):
            candidates.append(name)
    return candidates


def grade_response(text: str, case: CodingCase) -> tuple[int, list[str]]:
    notes: list[str] = []
    score = 100
    response = text or ""

    if len(response.strip()) < case.min_chars:
        score -= 25
        notes.append(f"too short: {len(response.strip())} chars")
    if case.max_chars and len(response.strip()) > case.max_chars:
        score -= 10
        notes.append(f"too long: {len(response.strip())} chars")

    for pattern in case.required_patterns:
        if not re.search(pattern, response, flags=re.IGNORECASE | re.MULTILINE):
            score -= 20
            notes.append(f"missing pattern: {pattern}")

    for pattern in case.forbidden_patterns:
        if re.search(pattern, response, flags=re.IGNORECASE | re.MULTILINE):
            score -= 25
            notes.append(f"forbidden pattern: {pattern}")

    if case.required_json_keys:
        _grade_json(response, case.required_json_keys, notes)

    if case.python_must_compile:
        _grade_python_compile(response, notes)

    if "traceback" in response.lower() or "[err]" in response.lower():
        score -= 25
        notes.append("backend error marker")

    return max(0, score - _note_penalty(notes, case)), notes


def _note_penalty(notes: list[str], case: CodingCase) -> int:
    penalty = 0
    if case.required_json_keys and any(n.startswith("json ") for n in notes):
        penalty += 35
    if case.python_must_compile and any(n.startswith("python ") for n in notes):
        penalty += 35
    return penalty


def _grade_json(response: str, required_keys: list[str], notes: list[str]) -> None:
    raw = response.strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        notes.append("json parse failed")
        return
    if not isinstance(data, dict):
        notes.append("json root is not object")
        return
    for key in required_keys:
        if key not in data:
            notes.append(f"json missing key: {key}")


def _grade_python_compile(response: str, notes: list[str]) -> None:
    code = _extract_python_code(response)
    if not code.strip():
        notes.append("python code missing")
        return
    try:
        compile(code, "<coding-eval>", "exec")
    except SyntaxError as exc:
        notes.append(f"python syntax error: {exc.msg}")


def _extract_python_code(response: str) -> str:
    match = re.search(r"```(?:python|py)?\s*(.*?)```", response, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return response.strip()


def run_eval(
    cases: list[CodingCase],
    backends: list[str],
    call_fn: Callable[[str, list[dict], int], str],
) -> list[EvalResult]:
    results: list[EvalResult] = []
    for backend in backends:
        for case in cases:
            messages = [{"role": "user", "content": case.prompt}]
            started = time.time()
            try:
                response = call_fn(backend, messages, case.max_tokens)
                latency_ms = int((time.time() - started) * 1000)
                score, notes = grade_response(response, case)
                results.append(
                    EvalResult(
                        backend=backend,
                        case_id=case.id,
                        score=score,
                        latency_ms=latency_ms,
                        ok=score >= 70,
                        notes=notes,
                        response_preview=_preview(response),
                    )
                )
            except Exception as exc:
                latency_ms = int((time.time() - started) * 1000)
                results.append(
                    EvalResult(
                        backend=backend,
                        case_id=case.id,
                        score=0,
                        latency_ms=latency_ms,
                        ok=False,
                        notes=[_format_exception(exc)],
                        response_preview="",
                    )
                )
    return results


def write_json_report(results: list[EvalResult], path: str | Path) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_markdown_report(results: list[EvalResult], path: str | Path) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Coding Backend Ranking",
        "",
        "> Generated by `scripts/eval_coding_backends.py`.",
        "",
        "| Backend | Avg Score | Passes | Avg Latency | Notes |",
        "|---|---:|---:|---:|---|",
    ]
    ranked = sorted(
        {r.backend for r in results},
        key=lambda backend: _ranking_key([r for r in results if r.backend == backend]),
    )
    for backend in ranked:
        rows = [r for r in results if r.backend == backend]
        avg_score = int(statistics.mean(r.score for r in rows))
        passes = sum(1 for r in rows if r.ok)
        avg_latency = int(statistics.mean(r.latency_ms for r in rows))
        notes = "; ".join(
            f"{r.case_id}: {', '.join(r.notes[:2])}" for r in rows if r.notes
        )
        lines.append(
            f"| `{backend}` | {avg_score} | {passes}/{len(rows)} | {avg_latency}ms | {notes or 'ok'} |"
        )
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _preview(text: str) -> str:
    return " ".join((text or "").split())[:280]


def _ranking_key(rows: list[EvalResult]) -> tuple[int, int, int, str]:
    avg_score = int(statistics.mean(r.score for r in rows))
    passes = sum(1 for r in rows if r.ok)
    avg_latency = int(statistics.mean(r.latency_ms for r in rows))
    return (-avg_score, -passes, avg_latency, rows[0].backend)


def _format_exception(exc: Exception) -> str:
    message = str(exc)
    if "WinError 10013" in message:
        message = "WinError 10013: socket access blocked by local OS/firewall policy"
    return f"call failed: {type(exc).__name__}: {message[:160]}"
