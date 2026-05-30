"""Structured debugging workflow: scan → graph retrieval → git log → test → report.

Investigates a file or error description by analyzing code structure,
finding related files, checking recent changes, and running relevant tests.
"""

from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path

from developer_skills import SkillResult

_log = logging.getLogger(__name__)


def investigate(target: str, *, cwd: str | None = None) -> SkillResult:
    """Run structured investigation on a file or error description.

    Steps:
    1. If target is a file path → scan with AST extractor
    2. Find related files via graph index
    3. Check recent git log for the file
    4. Run related tests if found
    5. Return structured report
    """
    t0 = time.time()
    details: list[str] = []
    evidence: list[str] = []

    path = Path(target) if Path(target).exists() else None
    if path and path.is_file():
        details.append(f"## File: {path}")
        _analyze_file(path, details, evidence)
        _find_related(path, details, evidence)
        _check_git_log(path, details, evidence)
    else:
        details.append(f"## Query: {target}")
        details.append("Target is not a file path — treating as error description.")
        _search_by_keywords(target, details, evidence)

    _run_related_tests(path, details, evidence)

    duration = (time.time() - t0) * 1000
    evidence.append(f"investigate_duration:{duration:.0f}ms")

    return SkillResult(
        ok=True,
        skill="investigate",
        summary=f"Investigation complete for: {target}",
        details=details,
        evidence=evidence,
    )


def _analyze_file(path: Path, details: list[str], evidence: list[str]) -> None:
    try:
        from code_context.ast_adapter import get_extractor
        suffix = path.suffix.lower()
        lang_map = {".py": "python", ".js": "javascript", ".ts": "typescript"}
        lang = lang_map.get(suffix, "python")
        extractor = get_extractor(lang)
        if extractor:
            ast = extractor.scan_file(path)
            details.append(f"Language: {ast.language}")
            details.append(f"Symbols: {len(ast.symbols)}")
            for s in ast.symbols[:10]:
                details.append(f"  - {s.kind}: {s.name} (line {s.line})")
            evidence.append(f"ast_symbols:{len(ast.symbols)}")
    except Exception as exc:
        details.append(f"AST analysis failed: {exc}")


def _find_related(path: Path, details: list[str], evidence: list[str]) -> None:
    try:
        from code_context.graph_index import build_graph_index
        g = build_graph_index()
        if g.edge_count > 0:
            results = g.search([path.name], max_depth=2, max_results=5)
            if results:
                details.append("## Related files:")
                for r in results:
                    details.append(f"  - {r.entity} (score: {r.score:.2f})")
                evidence.append(f"related_files:{len(results)}")
    except Exception as exc:
        _log.debug("graph search failed: %s", exc)


def _check_git_log(path: Path, details: list[str], evidence: list[str]) -> None:
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "-5", "--", str(path)],
            capture_output=True, text=True, timeout=5, cwd=path.parent,
        )
        if result.stdout.strip():
            details.append("## Recent git history:")
            for line in result.stdout.strip().split("\n"):
                details.append(f"  {line}")
            evidence.append("git_log_ok")
    except Exception as exc:
        _log.debug("developer_skills/investigate.py: {}", type(exc).__name__)


def _search_by_keywords(query: str, details: list[str], evidence: list[str]) -> None:
    try:
        from code_context.index_store import InMemoryCodeIndex
        idx = InMemoryCodeIndex()
        results = idx.search(query, limit=5)
        if results:
            details.append("## Matching files:")
            for r in results:
                details.append(f"  - {r.path}")
            evidence.append(f"keyword_matches:{len(results)}")
    except Exception as exc:
        _log.debug("developer_skills/investigate.py: {}", type(exc).__name__)


def _run_related_tests(
    path: Path | None, details: list[str], evidence: list[str],
) -> None:
    if not path or path.suffix != ".py":
        return
    test_path = path.parent.parent / "tests" / f"test_{path.stem}.py"
    if not test_path.exists():
        test_path = path.parent / f"test_{path.stem}.py"
    if not test_path.exists():
        return
    try:
        result = subprocess.run(
            ["python", "-m", "pytest", str(test_path), "-q", "--tb=short"],
            capture_output=True, text=True, timeout=30,
        )
        lines = result.stdout.strip().split("\n")
        details.append(f"## Tests ({test_path.name}):")
        for line in lines[-3:]:
            details.append(f"  {line}")
        evidence.append(f"tests_exit:{result.returncode}")
    except subprocess.TimeoutExpired:
        details.append("Tests timed out (30s)")
    except Exception as exc:
        details.append(f"Test run failed: {exc}")
