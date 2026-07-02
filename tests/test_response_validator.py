"""Tests for context_pipeline/response_validator.py — code validation."""

from context_pipeline.response_validator import (
    validate_response,
    _extract_code_blocks,
    _check_python_syntax,
    _check_security,
    _validate_block,
    CodeBlock,
)


class TestExtractCodeBlocks:
    def test_no_code_blocks(self):
        assert _extract_code_blocks("plain text") == []

    def test_single_code_block(self):
        blocks = _extract_code_blocks("```python\nprint('hello')\n```")
        assert len(blocks) == 1
        assert blocks[0].language == "python"
        assert "print" in blocks[0].code

    def test_multiple_code_blocks(self):
        text = "```py\na=1\n```\n```js\nconsole.log('x')\n```"
        blocks = _extract_code_blocks(text)
        assert len(blocks) == 2

    def test_code_block_without_language(self):
        blocks = _extract_code_blocks("```\nplain code\n```")
        assert len(blocks) == 1
        assert blocks[0].language == "unknown"

    def test_empty_code_block(self):
        blocks = _extract_code_blocks("```python\n```")
        assert len(blocks) == 0


class TestValidateResponse:
    def test_empty_response(self):
        result = validate_response("")
        assert result.passed is False
        assert result.score == 0.0

    def test_valid_python(self):
        response = "Here's the code:\n```python\nx = 1\ny = 2\nprint(x + y)\n```"
        result = validate_response(response)
        assert result.passed is True
        assert result.score >= 0.5

    def test_python_syntax_error(self):
        response = "```python\nx = \n```"
        result = validate_response(response)
        assert result.passed is False or result.score < 0.6

    def test_security_issue_detected(self):
        response = "```python\npassword = 'super_secret_12345'\n```"
        result = validate_response(response)
        assert "hardcoded_secret" in (result.security_issues or result.issues)

    def test_no_code_returns_valid(self):
        result = validate_response("Just a text response without code blocks.")
        assert result.score > 0.0

    def test_multiple_blocks_some_valid(self):
        response = "```python\nx = 1\n```\n```python\ny = \n```"
        result = validate_response(response)
        assert result.blocks_checked == 2


class TestCheckPythonSyntax:
    def test_valid_syntax(self):
        issues = _check_python_syntax("x = 1")
        assert len(issues) == 0

    def test_syntax_error(self):
        issues = _check_python_syntax("x = ")
        assert any("syntax_error" in i[0] for i in issues)

    def test_bare_except_detected(self):
        issues = _check_python_syntax("try:\n    pass\nexcept:\n    pass")
        assert any("bare_except" in i[1] for i in issues)

    def test_bare_except_pass_detected(self):
        issues = _check_python_syntax("try:\n    pass\nexcept Exception:\n    pass")
        assert any("bare_except_pass" in i[1] for i in issues)


class TestCheckSecurity:
    def test_hardcoded_secret_detected(self):
        issues = _check_security("password = 'my_secret_key_123456789'", "python")
        assert any("hardcoded_secret" in i[0] for i in issues)

    def test_eval_detected(self):
        issues = _check_security("eval(user_input)", "python")
        assert any("code_injection" in i[0] for i in issues)

    def test_os_system_detected(self):
        issues = _check_security("os.system('rm -rf /')", "python")
        assert any("shell_injection_os" in i[0] for i in issues)

    def test_verify_false_detected(self):
        issues = _check_security("verify = False", "python")
        assert any("ssl_bypass" in i[0] for i in issues)

    def test_clean_code_no_issues(self):
        issues = _check_security("print('hello')", "python")
        assert len(issues) == 0

    def test_unsafe_deserialization_detected(self):
        issues = _check_security("pickle.loads(data)", "python")
        assert any("unsafe_deserialization" in i[0] for i in issues)


class TestValidateBlock:
    def test_python_valid(self):
        block = CodeBlock(language="python", code="x = 1")
        issues = _validate_block(block)
        assert len(issues) == 0

    def test_python_security_issue(self):
        block = CodeBlock(language="python", code="password='secret_value_123'")
        issues = _validate_block(block)
        assert any("security" in i[0] for i in issues)

    def test_javascript_valid(self):
        block = CodeBlock(language="javascript", code="let x = 1;")
        issues = _validate_block(block)
        assert len(issues) == 0

    def test_unknown_language(self):
        block = CodeBlock(language="unknown", code="some code")
        issues = _validate_block(block)
        assert len(issues) == 0
