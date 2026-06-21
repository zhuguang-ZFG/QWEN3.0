"""Tests for response_builder usage estimation."""

from response_builder import build_anthropic_response, build_response, build_usage


def test_build_usage_estimates_non_zero_tokens():
    usage = build_usage("hello world", "assistant reply")
    assert usage["prompt_tokens"] > 0
    assert usage["completion_tokens"] > 0
    assert usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"]


def test_build_response_includes_estimated_usage():
    resp = build_response("id", "answer text", "longcat_chat", 12, prompt_text="user question")
    assert resp["usage"]["prompt_tokens"] > 0
    assert resp["usage"]["completion_tokens"] > 0


def test_build_anthropic_response_drops_hardcoded_input_tokens():
    resp = build_anthropic_response("id", "answer text", "longcat_chat", prompt_text="user question")
    assert resp["usage"]["input_tokens"] > 0
    assert resp["usage"]["output_tokens"] > 0
    assert resp["usage"]["input_tokens"] != 10


def test_estimate_token_count_handles_cjk():
    from response_builder import estimate_token_count

    assert estimate_token_count("你好世界") >= 2
    assert estimate_token_count("hello world") >= 2
