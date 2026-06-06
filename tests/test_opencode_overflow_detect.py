"""Tests for opencode_overflow_detect.py — enhanced overflow detection."""

import json

import pytest

from opencode_overflow_detect import (
    classify_overflow_severity,
    identify_overflow_provider,
    is_overflow_error,
    is_overflow_from_exception,
)


class TestIsOverflowError:
    """is_overflow_error() pattern matching tests."""

    # ── Provider-specific patterns ──

    def test_anthropic(self):
        assert is_overflow_error("prompt is too long for the model")

    def test_bedrock(self):
        assert is_overflow_error("input is too long for requested model")

    def test_openai(self):
        assert is_overflow_error("This model exceeds the context window size")

    def test_google(self):
        assert is_overflow_error("input token count of 50000 exceeds the maximum allowed")

    def test_xai(self):
        assert is_overflow_error("maximum prompt length is 131072 tokens")

    def test_groq(self):
        assert is_overflow_error("Please reduce the length of the messages")

    def test_openrouter(self):
        assert is_overflow_error("maximum context length is 128000 tokens")

    def test_copilot(self):
        assert is_overflow_error("exceeds the limit of 4096")

    def test_vllm_context_length(self):
        assert is_overflow_error("maximum context length is 32768 tokens")

    def test_vllm_only(self):
        assert is_overflow_error("context length is only 8192 tokens")

    def test_vllm_input_length(self):
        assert is_overflow_error("input length of 50000 exceeds the context length")

    def test_llamacpp(self):
        assert is_overflow_error("exceeds the available context size")

    def test_lmstudio(self):
        assert is_overflow_error("greater than the context length of 4096")

    def test_minimax(self):
        assert is_overflow_error("context window exceeds limit")

    def test_kimi(self):
        assert is_overflow_error("exceeded model token limit")

    def test_ollama(self):
        assert is_overflow_error("prompt too long; exceeded max context length")

    def test_mistral(self):
        assert is_overflow_error("too large for model with 32768 maximum context length")

    def test_zai(self):
        assert is_overflow_error("model_context_window_exceeded")

    def test_generic_context_length_exceeded(self):
        assert is_overflow_error("context_length_exceeded")

    def test_generic_request_entity(self):
        assert is_overflow_error("request entity too large")

    # ── HTTP status codes ──

    def test_413_auto_overflow(self):
        assert is_overflow_error(status_code=413)

    def test_400_no_body(self):
        assert is_overflow_error("400 status code (no body)")

    def test_403_no_body_not_overflow(self):
        # 403 is Forbidden, not overflow — only 400/413 no-body match (error.ts:58-62)
        assert not is_overflow_error("403 (no body)")

    def test_413_no_body(self):
        assert is_overflow_error("413 (no body)")

    # ── error.code detection ──

    def test_error_code_direct(self):
        assert is_overflow_error(error_code="context_length_exceeded")

    def test_error_code_in_body(self):
        body = json.dumps({"error": {"code": "context_length_exceeded", "message": "too long"}})
        assert is_overflow_error(response_body=body)

    def test_error_string_in_body(self):
        body = json.dumps({"error": "prompt is too long"})
        assert is_overflow_error(response_body=body)

    # ── Non-overflow cases ──

    def test_normal_error(self):
        assert not is_overflow_error("invalid API key")

    def test_rate_limit(self):
        assert not is_overflow_error("rate limit exceeded, try again later")

    def test_empty(self):
        assert not is_overflow_error("")

    def test_500_not_overflow(self):
        assert not is_overflow_error("internal server error", status_code=500)


class TestIdentifyOverflowProvider:
    """identify_overflow_provider() tests."""

    def test_anthropic(self):
        assert identify_overflow_provider("prompt is too long") == "anthropic"

    def test_kimi(self):
        assert identify_overflow_provider("exceeded model token limit") == "kimi"

    def test_google(self):
        result = identify_overflow_provider("input token count of 50000 exceeds the maximum")
        assert result == "google"

    def test_unknown(self):
        assert identify_overflow_provider("something went wrong") is None

    def test_empty(self):
        assert identify_overflow_provider("") is None


class TestClassifyOverflowSeverity:
    """classify_overflow_severity() tests."""

    def test_hard_413(self):
        assert classify_overflow_severity(status_code=413) == "hard"

    def test_hard_code(self):
        body = json.dumps({"error": {"code": "context_length_exceeded"}})
        assert classify_overflow_severity(response_body=body) == "hard"

    def test_soft_pattern(self):
        assert classify_overflow_severity("prompt is too long") == "soft"

    def test_none_normal(self):
        assert classify_overflow_severity("all good") == "none"


class TestIsOverflowFromException:
    """is_overflow_from_exception() tests."""

    def test_simple_exception(self):
        exc = Exception("prompt is too long")
        assert is_overflow_from_exception(exc) is True

    def test_normal_exception(self):
        exc = Exception("connection timeout")
        assert is_overflow_from_exception(exc) is False

    def test_exception_with_status(self):
        exc = Exception("error")
        exc.status_code = 413
        assert is_overflow_from_exception(exc) is True

    def test_exception_with_code(self):
        exc = Exception("overflow")
        exc.code = "context_length_exceeded"
        assert is_overflow_from_exception(exc) is True
