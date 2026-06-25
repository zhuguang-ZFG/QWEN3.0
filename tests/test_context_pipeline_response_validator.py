"""Tests for context_pipeline/response_validator.py — code/security validation (P2-7)."""

from __future__ import annotations

import pytest

from context_pipeline.response_validator import validate_response


def test_validate_empty_response():
    result = validate_response("")
    assert result.passed is False
    assert result.score == 0.0
    assert "empty_response" in result.issues


def test_validate_no_code_blocks():
    result = validate_response("This is plain text with no code.")
    assert result.passed is True
    assert result.blocks_checked == 0


def test_validate_python_syntax_ok():
    response = "```python\ndef foo():\n    return 1\n```"
    result = validate_response(response)
    assert result.passed is True
    assert result.blocks_checked == 1
    assert result.security_issues == []


def test_validate_python_syntax_error():
    response = "```python\ndef foo(\n```"
    result = validate_response(response)
    assert result.passed is False
    assert result.syntax_issues
    assert result.blocks_checked == 1


def test_validate_python_bare_except_pass():
    response = "```python\ntry:\n    pass\nexcept Exception:\n    pass\n```"
    result = validate_response(response)
    assert result.passed is False
    assert any("bare_except_pass" in issue for issue in result.syntax_issues)


def test_validate_security_hardcoded_secret():
    response = "```python\napi_key = 'supersecret12345678'\n```"
    result = validate_response(response)
    assert result.passed is False
    assert any("hardcoded_secret" in issue for issue in result.security_issues)


def test_validate_security_eval():
    response = "```python\neval(user_input)\n```"
    result = validate_response(response)
    assert result.passed is False
    assert any("code_injection" in issue for issue in result.security_issues)


def test_validate_security_os_system():
    response = "```python\nimport os\nos.system('ls')\n```"
    result = validate_response(response)
    assert result.passed is False
    assert any("shell_injection_os" in issue for issue in result.security_issues)


def test_validate_security_ssl_bypass():
    response = "```python\nrequests.get(url, verify=False)\n```"
    result = validate_response(response)
    assert result.passed is False
    assert any("ssl_bypass" in issue for issue in result.security_issues)


def test_validate_js_pattern_issues():
    response = "```javascript\nconst x = foo() => { return 1 }\n```"
    result = validate_response(response)
    assert result.blocks_checked == 1


def test_validate_multiple_blocks():
    response = "```python\ndef good():\n    return 1\n```\n```python\neval(x)\n```"
    result = validate_response(response)
    assert result.blocks_checked == 2
    assert result.passed is False
