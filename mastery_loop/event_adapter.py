"""Convert LiMa evidence into normalized mastery events."""
from __future__ import annotations

import re

from .models import MasteryEvent

FILE_RE = re.compile(r"([A-Za-z0-9_./\\-]+\.(?:py|ts|tsx|js|md|json|toml|yml|yaml))")


def _files(text: str) -> list[str]:
    seen: list[str] = []
    for match in FILE_RE.findall(text or ""):
        normalized = match.replace("\\", "/")
        if normalized not in seen:
            seen.append(normalized)
    return seen


def _modules(files: list[str]) -> list[str]:
    modules: list[str] = []
    for file in files:
        module = file.split("/", 1)[0] if "/" in file else file
        if module not in modules:
            modules.append(module)
    return modules


def from_pytest_output(project: str, output: str, evidence_ref: str = "") -> MasteryEvent:
    failed = " failed" in output or "ERROR" in output or "FAILED " in output
    files = _files(output)
    summary = "pytest failed" if failed else "pytest passed"
    return MasteryEvent(
        source="test",
        project=project,
        outcome="fail" if failed else "success",
        summary=f"{summary}: {output[:240]}",
        files=files,
        modules=_modules(files),
        score=-0.7 if failed else 0.5,
        severity="high" if failed else "info",
        evidence_ref=evidence_ref,
    )


def from_review_finding(
    project: str,
    severity: str,
    message: str,
    file: str = "",
    evidence_ref: str = "",
) -> MasteryEvent:
    sev = severity.lower()
    score = {"p0": -0.9, "p1": -0.7, "p2": -0.4}.get(sev, -0.2)
    files = [file] if file else _files(message)
    return MasteryEvent(
        source="review",
        project=project,
        outcome="fail" if sev in {"p0", "p1"} else "flaky",
        summary=message[:300],
        files=files,
        modules=_modules(files),
        score=score,
        severity=sev,
        evidence_ref=evidence_ref,
    )


def from_deploy_smoke(project: str, ok: bool, target: str, evidence_ref: str = "") -> MasteryEvent:
    return MasteryEvent(
        source="deploy",
        project=project,
        outcome="success" if ok else "fail",
        summary=f"deploy smoke {'passed' if ok else 'failed'} for {target}",
        modules=["deploy"],
        score=0.6 if ok else -0.8,
        severity="info" if ok else "high",
        evidence_ref=evidence_ref,
    )


def from_routing_failure(project: str, backend: str, failure_class: str, evidence_ref: str = "") -> MasteryEvent:
    return MasteryEvent(
        source="route",
        project=project,
        outcome="fail",
        summary=f"backend {backend} reported {failure_class}",
        modules=[f"backend:{backend}"],
        score=-0.5,
        severity="medium",
        evidence_ref=evidence_ref,
    )


def from_tool_audit(project: str, tool_name: str, allowed: bool, reason: str, evidence_ref: str = "") -> MasteryEvent:
    return MasteryEvent(
        source="tool",
        project=project,
        outcome="success" if allowed else "blocked",
        summary=f"tool {tool_name}: {reason}",
        modules=["tool_gateway"],
        score=0.2 if allowed else -0.4,
        severity="info" if allowed else "medium",
        evidence_ref=evidence_ref,
    )
