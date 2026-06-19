"""Response post-processor: validates code syntax + security in backend responses.

Extracts code blocks from responses, checks syntax (ast.parse for Python,
basic checks for other languages), scans for security issues, and returns
a quality verdict. Used by routing_engine to decide whether to retry.
"""

from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass, field
from typing import Any

_log = logging.getLogger(__name__)

_CODE_BLOCK_RE = re.compile(r"```(\w+)?\n(.*?)```", re.DOTALL)

_SECURITY_PATTERNS = [
    (re.compile(r"(?:password|secret|api_key|token)\s*=\s*['\"][^'\"]{8,}"), "hardcoded_secret"),
    (re.compile(r"\beval\s*\(|\bexec\s*\("), "code_injection"),
    (re.compile(r"\bos\.system\s*\("), "shell_injection_os"),
    (re.compile(r"\bos\.popen\s*\("), "shell_injection_os"),
    (re.compile(r"\b(?:subprocess\.(?:call|run|Popen)|os\.system)\(.*shell\s*=\s*True"), "command_injection"),
    (re.compile(r"verify\s*=\s*False"), "ssl_bypass"),
    (re.compile(r"pickle\.loads|yaml\.load\((?!.*Loader)"), "unsafe_deserialization"),
    (re.compile(r"subprocess\.call\(.*shell\s*=\s*True"), "shell_injection"),
]

_PYTHON_SYNTAX_ISSUES = [
    (re.compile(r"except\s+Exception\s*:\s*\n\s*pass"), "bare_except_pass"),
    (re.compile(r"except\s*:"), "bare_except"),
]

# JavaScript/TypeScript common issues (regex-based, no Node.js required)
_JS_SYNTAX_ISSUES = [
    (re.compile(r"const\s+\w+\s*=\s*\w+\s*\(\).*\{.*\}"), "arrow_missing"),
    (re.compile(r"await\s+(?![\w.({\[`$])"), "dangling_await"),
    (re.compile(r"\.then\s*\(\s*\)"), "empty_then"),
]


@dataclass
class CodeBlock:
    language: str
    code: str
    line_start: int = 0


@dataclass
class ValidationResult:
    passed: bool
    score: float  # 0.0 - 1.0
    issues: list[str] = field(default_factory=list)
    blocks_checked: int = 0
    security_issues: list[str] = field(default_factory=list)
    syntax_issues: list[str] = field(default_factory=list)


def validate_response(response: str, query: str = "") -> ValidationResult:
    """Validate code blocks in a response for syntax and security.

    Returns a ValidationResult with score 0-1 and categorized issues.
    """
    if _should_skip_validation("", None, response):
        empty_errors: dict[str, Any] = {
            "all": ["empty_response"],
            "security": [],
            "syntax": [],
            "score": 0.0,
        }
        return _format_validation_result(False, empty_errors, 0)

    blocks = _extract_code_blocks(response)
    passed, errors = _run_coding_validation(response, blocks, None)
    return _format_validation_result(passed, errors, len(blocks))


def _should_skip_validation(request_type: str, config: dict | None, response_text: str) -> bool:
    """Return True when validation should be short-circuited."""
    return not response_text or not response_text.strip()


def _run_coding_validation(
    response_text: str,
    code_blocks: list[CodeBlock],
    config: dict | None,
) -> tuple[bool, dict[str, Any]]:
    """Run syntax and security checks on extracted code blocks."""
    all_issues: list[str] = []
    security_issues: list[str] = []
    syntax_issues: list[str] = []
    blocks_with_issues = 0

    for block in code_blocks:
        block_issues = _validate_block(block)
        if block_issues:
            blocks_with_issues += 1
            for issue_type, detail in block_issues:
                all_issues.append(f"{block.language}:{issue_type}")
                if issue_type.startswith("security:"):
                    security_issues.append(detail)
                else:
                    syntax_issues.append(detail)

    total_blocks = max(len(code_blocks), 1)
    issue_ratio = blocks_with_issues / total_blocks
    score = max(0.0, 1.0 - issue_ratio * 0.5 - len(security_issues) * 0.15)
    if code_blocks and security_issues:
        score *= 0.5

    passed = score >= 0.6 and not security_issues
    errors: dict[str, Any] = {
        "all": all_issues,
        "security": security_issues,
        "syntax": syntax_issues,
        "score": score,
    }
    return passed, errors


def _format_validation_result(
    is_valid: bool,
    errors: dict[str, Any],
    code_count: int,
) -> ValidationResult:
    """Build a ValidationResult from validation outcome data."""
    return ValidationResult(
        passed=is_valid,
        score=round(errors.get("score", 0.0), 3),
        issues=errors.get("all", []),
        blocks_checked=code_count,
        security_issues=errors.get("security", []),
        syntax_issues=errors.get("syntax", []),
    )


def _extract_code_blocks(text: str) -> list[CodeBlock]:
    blocks: list[CodeBlock] = []
    for match in _CODE_BLOCK_RE.finditer(text):
        lang = (match.group(1) or "unknown").lower()
        code = match.group(2).strip()
        if code:
            blocks.append(CodeBlock(language=lang, code=code))
    return blocks


def _validate_block(block: CodeBlock) -> list[tuple[str, str]]:
    issues: list[tuple[str, str]] = []

    if block.language in ("python", "py"):
        py_issues = _check_python_syntax(block.code)
        issues.extend(py_issues)
    elif block.language in ("javascript", "js", "typescript", "ts", "tsx", "jsx"):
        js_issues = _check_js_syntax(block.code)
        issues.extend(js_issues)

    security = _check_security(block.code, block.language)
    issues.extend(security)

    return issues


def _check_python_syntax(code: str) -> list[tuple[str, str]]:
    issues: list[tuple[str, str]] = []
    try:
        ast.parse(code)
    except SyntaxError as exc:
        issues.append(("syntax_error", f"line {exc.lineno}: {exc.msg}"))
        return issues

    for pattern, issue_type in _PYTHON_SYNTAX_ISSUES:
        if pattern.search(code):
            issues.append(("quality", issue_type))

    return issues


def _check_js_syntax(code: str) -> list[tuple[str, str]]:
    """Check JavaScript/TypeScript for common issues using regex patterns."""
    issues: list[tuple[str, str]] = []
    for pattern, issue_type in _JS_SYNTAX_ISSUES:
        if pattern.search(code):
            issues.append(("js_pattern_issue", issue_type))
    return issues


def _check_security(code: str, language: str) -> list[tuple[str, str]]:
    issues: list[tuple[str, str]] = []
    for pattern, issue_type in _SECURITY_PATTERNS:
        if pattern.search(code):
            issues.append((f"security:{issue_type}", issue_type))
    return issues
