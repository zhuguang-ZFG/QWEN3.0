"""
quality_gate.py — 多维代码质量门（纯规则，不调模型）
5 个维度评分，总分 0-100，≥70 通过

增强功能:
  - 精确 Python 语法错误提取（行号 + 错误类型）
  - 类型注解检查（函数参数/返回值）
  - 增强 import 缺失检测
"""
import re
import ast
from typing import Optional


# ── Security Patterns ────────────────────────────────────────────────────────

_SECURITY_PATTERNS = [
    (r"f['\"].*(?:SELECT|INSERT|UPDATE|DELETE).*\{", "sql_injection"),
    (r"\.format\(.*\).*(?:SELECT|INSERT|UPDATE|DELETE)", "sql_injection"),
    (r"innerHTML\s*=\s*[^'\"]+(?:input|param|query|data)", "xss"),
    (r"(?:password|secret|api_key|token)\s*=\s*['\"][^'\"]{8,}", "hardcoded_secret"),
    (r"eval\(|exec\(", "code_injection"),
    (r"shell\s*=\s*True", "command_injection"),
    (r"verify\s*=\s*False", "ssl_bypass"),
    (r"pickle\.loads|yaml\.load\((?!.*Loader)", "unsafe_deserialization"),
]

# ── Deprecated Patterns ──────────────────────────────────────────────────────

_DEPRECATED = [
    (r"print\s+['\"]", "python2_print"),
    (r"\burllib2\b", "deprecated_urllib2"),
    (r"\.has_key\(", "deprecated_has_key"),
    (r"\braw_input\(", "deprecated_raw_input"),
    (r"\bxrange\(", "deprecated_xrange"),
]


def _extract_syntax_error_detail(code: str) -> Optional[str]:
    """Extract detailed Python syntax error info from code string.

    Returns:
        "line N: error_message" or None if valid.
    """
    try:
        ast.parse(code)
        return None
    except SyntaxError as e:
        lineno = getattr(e, "lineno", 0)
        msg = str(e.msg) if hasattr(e, "msg") else str(e)
        offset = getattr(e, "offset", 0)
        text = getattr(e, "text", "") if hasattr(e, "text") else ""
        if text:
            text = text.strip()
        parts = [f"line {lineno}: {msg}"]
        if text:
            parts.append(f"near '{text[:60]}'")
        return " — ".join(parts)


def _check_type_hints(python_blocks: list[str]) -> str:
    """Check if Python functions lack type annotations.

    Only flags issues if >50% of top-level functions lack annotations.

    Returns:
        Comma-separated function names lacking annotations, or empty string.
    """
    all_code = "\n".join(python_blocks)
    try:
        tree = ast.parse(all_code)
    except SyntaxError:
        return ""  # Can't check if syntax is invalid

    func_defs = [
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]

    if not func_defs:
        return ""

    unannotated: list[str] = []
    for func in func_defs:
        # Skip dunder methods and simple properties
        if func.name.startswith("_") and func.name.endswith("_"):
            continue
        if func.name == "main":
            continue

        # Check return annotation
        has_return = func.returns is not None
        # Check parameter annotations (skip 'self' and 'cls')
        params = [
            a for a in func.args.args
            if a.arg not in ("self", "cls")
        ]
        annotated_params = sum(1 for a in params if a.annotation is not None)

        if not has_return and annotated_params == 0 and params:
            unannotated.append(func.name)

    if not unannotated:
        return ""

    # Only flag if >50% are unannotated
    if len(unannotated) / len(func_defs) <= 0.5:
        return ""

    return ",".join(unannotated[:4])


def check(response: str, query: str) -> dict:
    """多维质量检查。返回 {passed, score, reasons, dimensions}"""
    if not response or not response.strip():
        return {"passed": False, "score": 0, "reasons": ["empty_response"],
                "dimensions": {}}

    text = response.strip()
    dims = {}

    # ── Dim 1: 基础质量 (0-20) ───────────────────────────────────────────
    d1_score = 20
    d1_issues = []

    # 拒绝回答
    refusal_patterns = [
        r"I (?:cannot|can't|am unable to|won't)",
        r"(?:抱歉|对不起).{0,10}(?:无法|不能|做不到)",
        r"as an AI.{0,20}(?:cannot|can't)",
    ]
    for p in refusal_patterns:
        if re.search(p, text[:200], re.I):
            d1_score -= 20
            d1_issues.append("refusal_detected")
            break

    # 重复检测
    sentences = [s.strip() for s in re.split(r'[。.!！?\n]', text)
                 if len(s.strip()) > 5]
    if len(sentences) > 3:
        if len(set(sentences)) < len(sentences) * 0.6:
            d1_score -= 10
            d1_issues.append("repetitive_content")

    # 思维链泄露
    if text.startswith("<think>") or "用户在问" in text[:50]:
        d1_score -= 20
        d1_issues.append("thinking_leak")

    dims["basic"] = max(0, d1_score)

    # ── Dim 2: 指令遵从 (0-25) ───────────────────────────────────────────
    d2_score = 25
    d2_issues = []
    is_code_query = bool(re.search(
        r"写|实现|代码|函数|code|implement|write|function|class|def ",
        query, re.I))

    if is_code_query:
        has_code = "```" in text or re.search(
            r"^(def |class |import |from |const |let |var |function )",
            text, re.M)
        if not has_code and len(text) > 50:
            d2_score -= 15
            d2_issues.append("no_code_in_coding_response")

        # 太短
        if len(text) < 30:
            d2_score -= 10
            d2_issues.append("too_short")

        # TODO/pass 占位符（不完整实现）
        if re.search(r"#\s*TODO|^\s*pass\s*$|^\s*\.\.\.\s*$", text, re.M):
            d2_score -= 8
            d2_issues.append("incomplete_implementation")

    dims["compliance"] = max(0, d2_score)

    # ── Dim 3: 安全性 (0-20) ─────────────────────────────────────────────
    d3_score = 20
    d3_issues = []
    code_text = "\n".join(re.findall(r"```\w*\n(.*?)```", text, re.S)) or text
    for pattern, vuln_type in _SECURITY_PATTERNS:
        if re.search(pattern, code_text, re.I | re.M):
            d3_score -= 10
            d3_issues.append(vuln_type)
    dims["security"] = max(0, d3_score)

    # ── Dim 4: 现代性 (0-15) ─────────────────────────────────────────────
    d4_score = 15
    d4_issues = []
    for pattern, issue_type in _DEPRECATED:
        if re.search(pattern, code_text, re.M):
            d4_score -= 5
            d4_issues.append(issue_type)
    dims["modernity"] = max(0, d4_score)

    # ── Dim 5: 代码正确性 (0-20) ─────────────────────────────────────────
    d5_score = 20
    d5_issues = []
    python_blocks = re.findall(r"```python\n(.*?)```", text, re.S)

    # AST 语法检查（含精确错误信息）
    syntax_errors: list[str] = []
    for i, block in enumerate(python_blocks[:3]):
        try:
            ast.parse(block)
        except SyntaxError as e:
            lineno = getattr(e, "lineno", 0)
            msg = str(e.msg) if hasattr(e, "msg") else str(e)
            syntax_errors.append(f"line {lineno}: {msg}" if lineno else msg)
            d5_score -= 10
            if i == 0:  # Only flag first block with syntax error
                break

    if syntax_errors:
        d5_issues.append(f"python_syntax_error:{';'.join(syntax_errors[:2])}")

    # import 完整性：用了但没 import
    if python_blocks and not syntax_errors:
        all_code = "\n".join(python_blocks)
        used_modules = set(re.findall(r"\b(\w+)\.\w+\(", all_code))
        imported = set(re.findall(r"(?:import|from)\s+(\w+)", all_code))
        # Built-in modules and common stdlib
        builtins = {"self", "cls", "str", "int", "list", "dict", "set",
                    "os", "re", "sys", "math", "json", "time", "datetime",
                    "pathlib", "Path", "io", "csv", "random", "collections",
                    "itertools", "functools", "typing", "logging", "enum",
                    "dataclasses", "contextlib", "asyncio", "subprocess",
                    "shutil", "tempfile", "hashlib", "uuid", "base64",
                    "threading", "queue", "copy", "types", "warnings",
                    "textwrap", "argparse", "configparser", "decimal",
                    "fractions", "statistics", "unittest", "pytest"}
        missing = used_modules - imported - builtins
        if missing:
            d5_score -= 5
            d5_issues.append(f"missing_imports:{','.join(sorted(list(missing))[:3])}")

    # 类型注解检查：检查函数是否缺少类型注解（Python 代码）
    if python_blocks and not syntax_errors:
        type_issues = _check_type_hints(python_blocks)
        if type_issues:
            d5_score -= 3
            d5_issues.append(f"missing_type_hints:{type_issues}")

    dims["correctness"] = max(0, d5_score)

    # ── Total Score ──────────────────────────────────────────────────────
    total = sum(dims.values())
    all_issues = d1_issues + d2_issues + d3_issues + d4_issues + d5_issues

    # Hard fail conditions (regardless of score)
    hard_fail = "refusal_detected" in all_issues or "thinking_leak" in all_issues

    return {
        "passed": total >= 70 and not hard_fail,
        "score": total,
        "reasons": all_issues,
        "dimensions": dims,
    }
