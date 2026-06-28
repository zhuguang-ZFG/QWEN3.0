"""Tests for http_response parsing helpers."""

from __future__ import annotations

import pytest

from http_errors import _extract_code
from http_response import _extract_answer, _parse_sse_chunk


def test_extract_answer_returns_empty_for_error_payload():
    assert _extract_answer({"error": {"message": "quota exceeded"}}, "openai") == ""


def test_extract_answer_handles_missing_choices():
    assert _extract_answer({"usage": {}}, "openai") == ""


def test_extract_answer_returns_content_when_present():
    data = {"choices": [{"message": {"content": "hello"}}]}
    assert _extract_answer(data, "openai") == "hello"


def test_extract_answer_returns_reasoning_content():
    data = {"choices": [{"message": {"reasoning_content": "think"}}]}
    assert _extract_answer(data, "openai") == "think"


def test_parse_sse_chunk_handles_missing_choices():
    assert _parse_sse_chunk('{"error": {"message": "oops"}}', "openai") == ""


def test_parse_sse_chunk_returns_delta_content():
    chunk = '{"choices": [{"delta": {"content": "hi"}}]}'
    assert _parse_sse_chunk(chunk, "openai") == "hi"


def test_parse_sse_chunk_returns_delta_reasoning():
    chunk = '{"choices": [{"delta": {"reasoning_content": "step"}}]}'
    assert _parse_sse_chunk(chunk, "openai") == "step"


def test_parse_sse_chunk_anthropic_text_delta():
    chunk = '{"type": "content_block_delta", "delta": {"type": "text_delta", "text": "hi"}}'
    assert _parse_sse_chunk(chunk, "anthropic") == "hi"


def test_extract_code_does_not_match_substring_401_in_quota_message():
    exc = RuntimeError("provider quota exceeded, billing code 401 invalid")
    assert _extract_code(exc) is None


def test_extract_code_does_not_match_substring_429_in_rate_limit_message():
    exc = RuntimeError("rate limit info: try again after 429 seconds")
    assert _extract_code(exc) is None


def test_extract_code_returns_http_status_error_code():
    class FakeResponse:
        status_code = 401

    class FakeExc(Exception):
        pass

    exc = FakeExc()

    # httpx.HTTPStatusError requires response; use BackendError-like attr
    class ErrorWithStatus(Exception):
        status_code = 403

    assert _extract_code(ErrorWithStatus("boom")) == 403


def test_extract_code_returns_none_for_plain_exception():
    assert _extract_code(ValueError("something else")) is None
