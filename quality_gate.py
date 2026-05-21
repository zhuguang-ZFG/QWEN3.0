"""
quality_gate.py — 代码质量门（纯规则，不调模型）
拦截低质量回复，决定是否需要强模型修复
"""
import re
import ast


def check(response: str, query: str) -> dict:
    """检查回复质量。返回 {passed: bool, reasons: [...]}"""
    reasons = []

    if not response or not response.strip():
        return {"passed": False, "reasons": ["empty_response"]}

    text = response.strip()

    # 1. 拒绝回答检测
    refusal_patterns = [
        r"I (?:cannot|can't|am unable to|won't)",
        r"(?:抱歉|对不起).{0,10}(?:无法|不能|做不到)",
        r"as an AI.{0,20}(?:cannot|can't)",
        r"I'm (?:sorry|afraid).{0,20}(?:can't|cannot|unable)",
    ]
    for p in refusal_patterns:
        if re.search(p, text[:200], re.I):
            reasons.append("refusal_detected")
            break

    # 2. 编程问题应该有代码
    is_code_query = bool(re.search(
        r"写|实现|代码|函数|code|implement|write|function|class|def |import",
        query, re.I))
    has_code = "```" in text or re.search(r"^(def |class |import |from |const |let |var |function )", text, re.M)
    if is_code_query and not has_code and len(text) > 50:
        reasons.append("no_code_in_coding_response")

    # 3. 重复检测
    sentences = [s.strip() for s in re.split(r'[。.!！?\n]', text) if len(s.strip()) > 5]
    if len(sentences) > 3:
        unique = set(sentences)
        if len(unique) < len(sentences) * 0.6:
            reasons.append("repetitive_content")

    # 4. 太短（编程问题期望详细回答）
    if is_code_query and len(text) < 30:
        reasons.append("too_short_for_code_query")

    # 5. 思维链泄露（二次防护）
    if text.startswith("<think>") or "用户在问" in text[:50]:
        reasons.append("thinking_leak")

    # 6. Python 语法检查（如果回复包含 Python 代码块）
    python_blocks = re.findall(r"```python\n(.*?)```", text, re.S)
    for block in python_blocks[:2]:
        try:
            ast.parse(block)
        except SyntaxError:
            reasons.append("python_syntax_error")
            break

    return {"passed": len(reasons) == 0, "reasons": reasons}
