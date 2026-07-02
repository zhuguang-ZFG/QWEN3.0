"""Routing engine result types."""

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


@dataclass
class PickResult:
    """选路结果（classify → inject → select → skills/compress，不执行 HTTP）。"""

    backend: str
    backends: list[str]
    messages: list[dict]
    request_type: str = "chat"
    scenario: str = ""
    retrieval_context: str = ""
    sticky_key: str = ""
