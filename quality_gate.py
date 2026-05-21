"""
quality_gate.py — 多维代码质量门（纯规则，不调模型）
5 个维度评分，总分 0-100，≥70 通过
"""
import re
import ast


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
    for block in python_blocks[:3]:
        try:
            ast.parse(block)
        except SyntaxError:
            d5_score -= 10
            d5_issues.append("python_syntax_error")
            break

    # import 完整性：用了但没 import
    if python_blocks:
        all_code = "\n".join(python_blocks)
        used_modules = set(re.findall(r"\b(\w+)\.\w+\(", all_code))
        imported = set(re.findall(r"(?:import|from)\s+(\w+)", all_code))
        missing = used_modules - imported - {"self", "cls", "str", "int",
                                              "list", "dict", "set", "os",
                                              "re", "sys", "math", "json"}
        if missing:
            d5_score -= 5
            d5_issues.append(f"missing_imports:{','.join(list(missing)[:3])}")

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
