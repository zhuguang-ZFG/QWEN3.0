"""Code review with confidence scoring and severity classification.

Parses changes, checks against coding standards, scores confidence per
finding, and returns structured results with file:line references.
"""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path

from developer_skills import SkillResult

_log = logging.getLogger(__name__)

_BARE_EXCEPT_RE = re.compile(r"except\s+Exception\s*:\s*\n\s*pass")
_HARDcoded_SECRET_RE = re.compile(r"""(?:api_key|password|secret|token)\s*=\s*['"][^'"]{8,}['"]""")
_DEEP_NESTING_RE = re.compile(r"^(\s{20,})\S", re.MULTILINE)
_LONG_FUNC_RE = re.compile(r"^(?:def|async def)\s+\w+", re.MULTILINE)
_MAGIC_NUMBER_RE = re.compile(r"(?<!=)\s(\d{3,})\b")


def review(target: str) -> SkillResult:
    """Review a file or directory for code quality issues.

    Returns findings with severity (info/warning/error), confidence (0-1),
    and file:line references.
    """
    t0 = time.time()
    details: list[str] = []
    evidence: list[str] = []
    findings_count = 0

    path = Path(target)
    if path.is_file():
        findings_count = _review_file(path, details, evidence)
    elif path.is_dir():
        for py_file in sorted(path.rglob("*.py")):
            if "venv" in str(py_file) or "__pycache__" in str(py_file):
                continue
            findings_count += _review_file(py_file, details, evidence)
    else:
        return SkillResult(
            ok=False, skill="review",
            summary=f"Target not found: {target}",
        )

    duration = (time.time() - t0) * 1000
    evidence.append(f"review_duration:{duration:.0f}ms")
    evidence.append(f"findings_count:{findings_count}")

    severity_counts = {"error": 0, "warning": 0, "info": 0}
    for line in details:
        if "[error]" in line.lower():
            severity_counts["error"] += 1
        elif "[warning]" in line.lower():
            severity_counts["warning"] += 1
        elif "[info]" in line.lower():
            severity_counts["info"] += 1

    summary = (
        f"Review complete: {findings_count} findings "
        f"({severity_counts['error']} errors, "
        f"{severity_counts['warning']} warnings, "
        f"{severity_counts['info']} info)"
    )

    return SkillResult(
        ok=True,
        skill="review",
        summary=summary,
        details=details,
        evidence=evidence,
    )


def _review_file(path: Path, details: list[str], evidence: list[str]) -> int:
    try:
        source = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return 0

    lines = source.split("\n")
    findings = 0

    for i, line in enumerate(lines, 1):
        ref = f"{path.name}:{i}"

        if re.match(r"\s*except\s+Exception\s*:\s*$", line):
            next_line = lines[i] if i < len(lines) else ""
            if re.match(r"\s*pass\s*$", next_line):
                details.append(f"[error] {ref}: bare except Exception: pass (confidence: 0.95)")
                findings += 1

        if _HARDcoded_SECRET_RE.search(line):
            details.append(f"[error] {ref}: possible hardcoded secret (confidence: 0.85)")
            findings += 1

        if _DEEP_NESTING_RE.match(line):
            details.append(f"[warning] {ref}: deep nesting >4 levels (confidence: 0.7)")
            findings += 1

    if len(lines) > 300:
        details.append(
            f"[warning] {path.name}: file exceeds 300 lines ({len(lines)}) (confidence: 0.9)"
        )
        findings += 1

    func_starts = _LONG_FUNC_RE.findall(source)
    if func_starts:
        details.append(
            f"[info] {path.name}: {len(func_starts)} functions defined (confidence: 0.6)"
        )

    evidence.append(f"file_lines:{len(lines)}")
    return findings
