"""Shared routing engine dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RouteResult:
    backend: str = ""
    answer: str = ""
    request_type: str = "chat"
    scenario: str = ""
    ms: int = 0
    fallback_used: bool = False
    skills_injected: list = field(default_factory=list)
    retrieval_context: str = ""
    usage: dict | None = None
    injection_meta: dict = field(default_factory=dict)
