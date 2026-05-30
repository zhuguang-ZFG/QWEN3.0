"""Tests for B2: response post-processing (syntax + security validation)."""

from __future__ import annotations


from context_pipeline.response_validator import (
    validate_response,
    _extract_code_blocks,
    _check_python_syntax,
    _check_security,
)


class TestExtractCodeBlocks:
    def test_extracts_python_block(self):
        text = "Here is code:\n```python\ndef foo(): pass\n```\nDone."
        blocks = _extract_code_blocks(text)
        assert len(blocks) == 1
        assert blocks[0].language == "python"
        assert "def foo" in blocks[0].code

    def test_extracts_multiple_blocks(self):
        text = "```python\nx = 1\n```\n\n```js\nconst y = 2;\n```"
        blocks = _extract_code_blocks(text)
        assert len(blocks) == 2

    def test_no_blocks(self):
        blocks = _extract_code_blocks("Just plain text, no code.")
        assert len(blocks) == 0

    def test_empty_code_block(self):
        blocks = _extract_code_blocks("```\n\n```")
        assert len(blocks) == 0


class TestPythonSyntax:
    def test_valid_syntax(self):
        issues = _check_python_syntax("def foo():\n    return 42")
        assert len(issues) == 0

    def test_syntax_error(self):
        issues = _check_python_syntax("def foo(")
        assert len(issues) == 1
        assert issues[0][0] == "syntax_error"

    def test_bare_except(self):
        issues = _check_python_syntax("try:\n    pass\nexcept:\n    pass")
        assert any("bare_except" in i[1] for i in issues)


class TestSecurity:
    def test_hardcoded_secret(self):
        issues = _check_security('password = "mysecretpassword123"', "python")
        assert any("hardcoded_secret" in i[1] for i in issues)

    def test_code_injection(self):
        issues = _check_security('eval(user_input)', "python")
        assert any("code_injection" in i[1] for i in issues)

    def test_shell_true(self):
        issues = _check_security('subprocess.call(cmd, shell=True)', "python")
        assert any("command_injection" in i[1] or "shell_injection" in i[1] for i in issues)

    def test_clean_code(self):
        issues = _check_security('x = 42\nprint(x)', "python")
        assert len(issues) == 0


class TestValidateResponse:
    def test_empty_response(self):
        result = validate_response("")
        assert result.passed is False
        assert result.score == 0.0

    def test_clean_python_response(self):
        result = validate_response("Here's the code:\n```python\ndef hello():\n    return 'world'\n```")
        assert result.passed is True
        assert result.score >= 0.8
        assert result.blocks_checked == 1

    def test_syntax_error_response(self):
        result = validate_response("```python\ndef foo(\n```")
        assert result.passed is False
        assert len(result.syntax_issues) > 0

    def test_security_issue_response(self):
        result = validate_response('```python\npassword = "secret123456"\n```')
        assert result.passed is False
        assert len(result.security_issues) > 0
        assert result.score < 0.5

    def test_mixed_blocks_one_bad(self):
        result = validate_response(
            "First block:\n```python\ndef ok(): pass\n```\n"
            "Second block:\n```python\ndef bad(\n```"
        )
        assert result.blocks_checked == 2
        assert len(result.syntax_issues) > 0

    def test_no_code_blocks(self):
        result = validate_response("Just a text answer with no code.")
        assert result.passed is True
        assert result.score >= 0.8

    def test_security_penalizes_score(self):
        clean = validate_response("```python\ndef ok(): pass\n```")
        dirty = validate_response("```python\neval('dangerous')\n```")
        assert dirty.score < clean.score
