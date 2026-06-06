"""test_code_orchestrator.py — 编程模型塔测试"""

from code_orchestrator import classify_code_tier
from intent_templates import amplify_intent, match_template
from quality_gate import check


class TestIntentTemplates:
    def test_match_sort(self):
        assert match_template("写个排序") is not None
        assert "排序" in match_template("写个排序")

    def test_match_api(self):
        assert match_template("implement user API") is not None

    def test_no_match(self):
        assert match_template("今天天气怎么样") is None

    def test_amplify_with_match(self):
        result = amplify_intent("写个爬虫")
        assert "用户原始需求" in result

    def test_amplify_no_match(self):
        result = amplify_intent("hello world")
        assert result == "hello world"


class TestQualityGate:
    def test_pass_good_code(self):
        code = "```python\ndef add(a, b):\n    return a + b\n```"
        assert check(code, "写加法函数")["passed"] is True

    def test_fail_empty(self):
        assert check("", "写代码")["passed"] is False

    def test_fail_refusal(self):
        r = check("I cannot help with that request", "写代码")
        assert r["passed"] is False
        assert "refusal_detected" in r["reasons"]

    def test_fail_no_code(self):
        r = check("排序是一种算法，它可以把数据按顺序排列。" * 3, "写个排序函数")
        assert "no_code_in_coding_response" in r["reasons"]

    def test_fail_repetitive(self):
        text = "这是一段重复的内容啊。这是一段重复的内容啊。这是一段重复的内容啊。这是一段重复的内容啊。这是一段重复的内容啊。另外一句话。"
        r = check(text, "解释一下")
        assert "repetitive_content" in r["reasons"]

    def test_fail_thinking_leak(self):
        r = check("<think>用户在问什么</think>答案是42", "问题")
        assert "thinking_leak" in r["reasons"]

    def test_fail_syntax_error(self):
        code = "```python\ndef broken(\n```"
        r = check(code, "写函数")
        assert "python_syntax_error" in r["reasons"]


class TestClassifyTier:
    def test_simple(self):
        assert classify_code_tier("import os") == "simple"

    def test_standard(self):
        assert classify_code_tier("写一个用户注册功能") == "standard"

    def test_complex_refactor(self):
        assert classify_code_tier("重构整个认证系统，涉及多文件改动") == "complex"

    def test_complex_long_query(self):
        assert classify_code_tier("x " * 800) == "complex"
