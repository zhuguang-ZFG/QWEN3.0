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

# 高置信度注入模式（明确试图覆盖系统指令/越狱）→ 直接 BLOCK（AUDIT-3-P3）
_INJECTION_BLOCK_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"you\s+are\s+now\s+a\s+different",
    r"system\s*:\s*you\s+are",
    r"<\|im_start\|>",
    r"\[INST\]",
    r"<<SYS>>",
    # 中文：明确的越狱/模式切换/指令覆盖（AUDIT-3-P1）
    r"忽略.{0,8}(指令|规则|提示|设定|约束|上文|系统)",
    r"无视.{0,8}(指令|规则|约束|上文|系统)",
    r"进入.{0,4}(开发者|调试|管理员|上帝|越狱|root|admin)(模式|权限)",
    r"越狱|jailbreak|DAN\s*模式|\bDAN\b",
]

# 可疑模式（可能是正常对话，降级为 WARN 不阻断）
_INJECTION_WARN_PATTERNS = [
    r"从现在.{0,4}(你(是|扮演)|进入|切换)",
    r"扮演.{0,6}(不同|其他|另外|新)的(角色|身份|人)",
    r"你的(新指令|新身份|真实身份)是",
    r"系统[:：]\s*你(现在|是)",
]

_INJECTION_BLOCK_RE = re.compile("|".join(_INJECTION_BLOCK_PATTERNS), re.IGNORECASE)
_INJECTION_WARN_RE = re.compile("|".join(_INJECTION_WARN_PATTERNS), re.IGNORECASE)

MAX_INPUT_CHARS = 200000
MAX_MESSAGES = 100


def check_injection(messages: list[dict]) -> GuardrailResult:
    """Detect prompt injection attempts in user messages.

    AUDIT-3-P1/P3: 高置信度越狱/指令覆盖模式直接 BLOCK（阻断请求），
    可疑角色扮演模式降级为 WARN（记日志但不阻断，避免误伤正常对话）。
    """
    block_violations = []
    warn_violations = []
    for msg in messages:
        if msg.get("role") != "user":
            continue
        content = msg.get("content", "")
        if not isinstance(content, str):
            continue
        if _INJECTION_BLOCK_RE.search(content):
            block_violations.append("injection_pattern_blocked")
            break
        if _INJECTION_WARN_RE.search(content):
            warn_violations.append("injection_pattern_suspected")
    if block_violations:
        return GuardrailResult(
            passed=False,
            violations=block_violations,
            severity=GuardrailSeverity.BLOCK,
        )
    return GuardrailResult(
        passed=len(warn_violations) == 0,
        violations=warn_violations,
        severity=GuardrailSeverity.WARN,
    )


def check_input_length(messages: list[dict]) -> GuardrailResult:
    """Validate input doesn't exceed safe limits."""
    violations = []
    total_chars = sum(len(str(m.get("content", ""))) for m in messages)
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
        if not check.passed:
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
