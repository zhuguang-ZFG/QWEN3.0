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
    if not response or not response.strip():
        return ValidationResult(passed=False, score=0.0, issues=["empty_response"])

    blocks = _extract_code_blocks(response)
    all_issues: list[str] = []
    security_issues: list[str] = []
    syntax_issues: list[str] = []
    blocks_with_issues = 0

    for block in blocks:
        block_issues = _validate_block(block)
        if block_issues:
            blocks_with_issues += 1
            for issue_type, detail in block_issues:
                all_issues.append(f"{block.language}:{issue_type}")
                if issue_type.startswith("security:"):
                    security_issues.append(detail)
                else:
                    syntax_issues.append(detail)

    total_blocks = max(len(blocks), 1)
    issue_ratio = blocks_with_issues / total_blocks
    score = max(0.0, 1.0 - issue_ratio * 0.5 - len(security_issues) * 0.15)

    has_code_blocks = len(blocks) > 0
    any(kw in query.lower() for kw in [
        "code", "function", "class", "implement", "write", "fix", "refactor",
        "代码", "函数", "实现", "编写", "修复", "重构",
    ])

    if has_code_blocks and security_issues:
        score *= 0.5

    passed = score >= 0.6 and not security_issues

    return ValidationResult(
        passed=passed,
        score=round(score, 3),
        issues=all_issues,
        blocks_checked=len(blocks),
        security_issues=security_issues,
        syntax_issues=syntax_issues,
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
