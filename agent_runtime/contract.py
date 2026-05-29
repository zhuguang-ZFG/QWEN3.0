"""Typed task, step, and result schemas for the agent runtime.

Serialization is sanitized so task artifacts do not expose API keys, tokens,
passwords, or raw secret-bearing prompts.
"""

from __future__ import annotations

import time
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


_REDACTED = "[REDACTED]"
_SECRET_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer ",
    "cookie",
    "credential",
    "password",
    "secret",
    "token=",
)
_SECRET_TOKEN_RE = re.compile(r"(^|[^a-zA-Z0-9])sk-[a-zA-Z0-9_-]{6,}")


class AgentRunStatus(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepKind(str, Enum):
    SUMMARIZE = "summarize"
    RETRIEVE_CONTEXT = "retrieve_context"
    RUN_TESTS = "run_tests"
    REVIEW = "review"
    SHELL_COMMAND = "shell_command"
    HTTP_CALL = "http_call"
    NOOP = "noop"


@dataclass
class AgentStep:
    step_id: str
    kind: StepKind
    goal: str = ""
    allowed_tools: list[str] = field(default_factory=list)
    command: str = ""
    timeout_sec: float = 30.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": redact(self.step_id),
            "kind": self.kind.value,
            "goal": redact(self.goal),
            "allowed_tools": [redact(tool) for tool in self.allowed_tools],
            "command": redact(self.command),
            "timeout_sec": self.timeout_sec,
            "metadata": redact_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentStep":
        return cls(
            step_id=str(data.get("step_id", "")),
            kind=_parse_enum(StepKind, data.get("kind"), StepKind.NOOP),
            goal=str(data.get("goal", "")),
            allowed_tools=_string_list(data.get("allowed_tools")),
            command=str(data.get("command", "")),
            timeout_sec=_safe_float(data.get("timeout_sec", 30.0)),
            metadata=_dict_or_empty(data.get("metadata")),
        )


@dataclass
class StepResult:
    step_id: str
    ok: bool
    output: str = ""
    error: str = ""
    evidence: list[str] = field(default_factory=list)
    duration_ms: float = 0.0
    blocked: bool = False
    blocked_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": redact(self.step_id),
            "ok": self.ok,
            "output": redact(self.output),
            "error": redact(self.error),
            "evidence": [redact(item) for item in self.evidence],
            "duration_ms": self.duration_ms,
            "blocked": self.blocked,
            "blocked_reason": redact(self.blocked_reason),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StepResult":
        return cls(
            step_id=str(data.get("step_id", "")),
            ok=bool(data.get("ok", False)),
            output=str(data.get("output", "")),
            error=str(data.get("error", "")),
            evidence=_string_list(data.get("evidence")),
            duration_ms=_safe_float(data.get("duration_ms", 0.0)),
            blocked=bool(data.get("blocked", False)),
            blocked_reason=str(data.get("blocked_reason", "")),
        )


@dataclass
class AgentTask:
    task_id: str
    goal: str = ""
    workspace: str = ""
    allowed_tools: list[str] = field(default_factory=list)
    authority_budget: int = 3
    steps: list[AgentStep] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    status: AgentRunStatus = AgentRunStatus.PENDING
    audit_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": redact(self.task_id),
            "goal": redact(self.goal),
            "workspace": redact(self.workspace),
            "allowed_tools": [redact(tool) for tool in self.allowed_tools],
            "authority_budget": self.authority_budget,
            "steps": [step.to_dict() for step in self.steps],
            "created_at": self.created_at,
            "status": self.status.value,
            "audit_refs": [redact(ref) for ref in self.audit_refs],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentTask":
        return cls(
            task_id=str(data.get("task_id", "")),
            goal=str(data.get("goal", "")),
            workspace=str(data.get("workspace", "")),
            allowed_tools=_string_list(data.get("allowed_tools")),
            authority_budget=_safe_int(data.get("authority_budget", 3)),
            steps=[
                AgentStep.from_dict(item)
                for item in data.get("steps", [])
                if isinstance(item, dict)
            ],
            created_at=_safe_float(data.get("created_at", time.time())),
            status=_parse_enum(
                AgentRunStatus,
                data.get("status"),
                AgentRunStatus.PENDING,
            ),
            audit_refs=_string_list(data.get("audit_refs")),
        )


@dataclass
class AgentRunResult:
    task_id: str
    status: AgentRunStatus
    steps: list[StepResult] = field(default_factory=list)
    total_ms: float = 0.0
    error: str = ""
    audit_refs: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status == AgentRunStatus.COMPLETED

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": redact(self.task_id),
            "status": self.status.value,
            "steps": [step.to_dict() for step in self.steps],
            "total_ms": round(self.total_ms, 1),
            "error": redact(self.error),
            "audit_refs": [redact(ref) for ref in self.audit_refs],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentRunResult":
        return cls(
            task_id=str(data.get("task_id", "")),
            status=_parse_enum(
                AgentRunStatus,
                data.get("status"),
                AgentRunStatus.FAILED,
            ),
            steps=[
                StepResult.from_dict(item)
                for item in data.get("steps", [])
                if isinstance(item, dict)
            ],
            total_ms=_safe_float(data.get("total_ms", 0.0)),
            error=str(data.get("error", "")),
            audit_refs=_string_list(data.get("audit_refs")),
        )


def redact(text: object) -> str:
    value = str(text)
    lowered = value.lower()
    if any(marker in lowered for marker in _SECRET_MARKERS):
        return _REDACTED
    if _SECRET_TOKEN_RE.search(value):
        return _REDACTED
    return value


def redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            safe_key = _REDACTED if _looks_secret_key(key_text) else redact(key_text)
            redacted[safe_key] = redact_value(item)
        return redacted
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_value(item) for item in value)
    if isinstance(value, str):
        return redact(value)
    return value


def _looks_secret_key(key: str) -> bool:
    lowered = key.lower()
    if any(marker.strip(" =") in lowered for marker in _SECRET_MARKERS):
        return True
    return bool(_SECRET_TOKEN_RE.search(key))


def _parse_enum(enum_type: type[Enum], value: Any, fallback: Any) -> Any:
    try:
        return enum_type(str(value))
    except ValueError:
        return fallback


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}
