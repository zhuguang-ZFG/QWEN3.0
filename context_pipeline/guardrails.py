"""Guardrails — input/output safety validation for the routing pipeline.

Based on OpenAI Agents guardrails pattern:
- Input guardrails: validate before routing (injection, length, format)
- Output guardrails: validate after response (safety, completeness)
- Configurable severity: block, warn, or log
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class GuardrailSeverity(Enum):
    BLOCK = "block"
    WARN = "warn"
    LOG = "log"


@dataclass
class GuardrailResult:
    """Result of a guardrail check."""

    passed: bool
    violations: list[str] = field(default_factory=list)
    severity: GuardrailSeverity = GuardrailSeverity.LOG


# ─── Input Guardrails ────────────────────────────────────────────────────────

_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"you\s+are\s+now\s+a\s+different",
    r"system\s*:\s*you\s+are",
    r"<\|im_start\|>",
    r"\[INST\]",
    r"<<SYS>>",
]

_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)

MAX_INPUT_CHARS = 200000
MAX_MESSAGES = 100


def check_injection(messages: list[dict]) -> GuardrailResult:
    """Detect prompt injection attempts in user messages."""
    violations = []
    for msg in messages:
        if msg.get("role") != "user":
            continue
        content = msg.get("content", "")
        if isinstance(content, str) and _INJECTION_RE.search(content):
            violations.append(f"injection_pattern_detected")
            break
    return GuardrailResult(
        passed=len(violations) == 0,
        violations=violations,
        severity=GuardrailSeverity.WARN,
    )


def check_input_length(messages: list[dict]) -> GuardrailResult:
    """Validate input doesn't exceed safe limits."""
    violations = []
    total_chars = sum(
        len(str(m.get("content", ""))) for m in messages
    )
    if total_chars > MAX_INPUT_CHARS:
        violations.append(f"input_too_long:{total_chars}")
    if len(messages) > MAX_MESSAGES:
        violations.append(f"too_many_messages:{len(messages)}")
    return GuardrailResult(
        passed=len(violations) == 0,
        violations=violations,
        severity=GuardrailSeverity.BLOCK,
    )


def check_format(messages: list[dict]) -> GuardrailResult:
    """Validate message format (required fields, valid roles)."""
    violations = []
    valid_roles = {"system", "user", "assistant", "tool"}
    for i, msg in enumerate(messages):
        if not isinstance(msg, dict):
            violations.append(f"msg_{i}_not_dict")
            continue
        role = msg.get("role", "")
        if role not in valid_roles:
            violations.append(f"msg_{i}_invalid_role:{role}")
        if "content" not in msg and "tool_calls" not in msg:
            violations.append(f"msg_{i}_no_content")
    return GuardrailResult(
        passed=len(violations) == 0,
        violations=violations,
        severity=GuardrailSeverity.BLOCK,
    )


# ─── Output Guardrails ───────────────────────────────────────────────────────

def check_output_safety(response_text: str) -> GuardrailResult:
    """Check response for unsafe content patterns."""
    violations = []
    if not response_text or len(response_text.strip()) < 2:
        violations.append("empty_output")
    dangerous_patterns = [
        r"rm\s+-rf\s+/",
        r"DROP\s+TABLE",
        r"DELETE\s+FROM\s+\w+\s*;?\s*$",
    ]
    for pattern in dangerous_patterns:
        if re.search(pattern, response_text, re.IGNORECASE):
            violations.append(f"dangerous_command:{pattern[:20]}")
    return GuardrailResult(
        passed=len(violations) == 0,
        violations=violations,
        severity=GuardrailSeverity.WARN,
    )


# ─── Combined Guardrail Runner ───────────────────────────────────────────────

def run_input_guardrails(messages: list[dict]) -> GuardrailResult:
    """Run all input guardrails. Returns combined result."""
    checks = [
        check_format(messages),
        check_input_length(messages),
        check_injection(messages),
    ]
    all_violations = []
    max_severity = GuardrailSeverity.LOG
    for check in checks:
        all_violations.extend(check.violations)
        if check.severity == GuardrailSeverity.BLOCK:
            max_severity = GuardrailSeverity.BLOCK
        elif check.severity == GuardrailSeverity.WARN and max_severity != GuardrailSeverity.BLOCK:
            max_severity = GuardrailSeverity.WARN
    return GuardrailResult(
        passed=len(all_violations) == 0,
        violations=all_violations,
        severity=max_severity,
    )
