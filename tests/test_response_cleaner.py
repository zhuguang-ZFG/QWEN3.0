"""Tests for the response_cleaner package."""

import pytest

from response_cleaner import (
    BRAND_PATTERNS,
    CLEAN_PATTERNS,
    StreamIdentitySanitizer,
    _is_backend_error,
    _looks_like_self_identity,
    apply_identity_cleaning,
    clean_response,
)
from response_cleaner.patterns import _build_brand_re


def test_brand_regex_matches_case_insensitive():
    pattern = _build_brand_re("claude")
    assert pattern.search("I am Claude 3.5")
    assert pattern.search("CLAUDE")


def test_brand_regex_does_not_eat_cjk_context():
    pattern = _build_brand_re("豆包")
    # Should match "豆包" but not consume the following verb
    text = "豆包可以帮你"
    match = pattern.search(text)
    assert match is not None
    assert match.group(0) == "豆包"


def test_clean_patterns_include_brand_and_identity():
    assert len(CLEAN_PATTERNS) == len(BRAND_PATTERNS) + len([
        p for p in CLEAN_PATTERNS if p not in BRAND_PATTERNS
    ])


def test_apply_identity_cleaning_replaces_known_brands():
    text = "As Claude, I can help you."
    cleaned = apply_identity_cleaning(text)
    assert "Claude" not in cleaned
    assert "LiMa" in cleaned


def test_apply_identity_cleaning_preserves_unrelated_text():
    text = "The quick brown fox jumps over the lazy dog."
    assert apply_identity_cleaning(text) == text


def test_looks_like_self_identity_detects_introductions():
    assert _looks_like_self_identity("I am Claude, an AI assistant.")
    assert _looks_like_self_identity("我是 Kimi，由月之暗面开发")
    assert _looks_like_self_identity("This is Gemini speaking.")
    assert not _looks_like_self_identity("The weather is nice today.")


@pytest.mark.parametrize(
    "text,expected",
    [
        ("服务繁忙，请稍后重试", True),
        ("服务器繁忙，请稍后再试", True),
        ("Rate limit exceeded", True),
        ("The server is busy because of the overloaded queue" + " x" * 200, False),  # >200 chars
        ("Here is the result", False),
        ("", False),
    ],
)
def test_is_backend_error(text, expected):
    assert _is_backend_error(text) is expected


def test_clean_response_strips_think_blocks():
    text = "<think>some reasoning</think>Hello!"
    assert clean_response(text) == "Hello!"


def test_clean_response_strips_unclosed_think():
    assert clean_response("<think>some reasoning") == ""


def test_clean_response_returns_empty_for_backend_error():
    assert clean_response("服务繁忙，请稍后重试") == ""


def test_clean_response_replaces_identity_introduction():
    result = clean_response("I am Kimi, developed by Moonshot AI.")
    assert "Kimi" not in result
    assert "Moonshot" not in result
    assert "LiMa" in result


def test_clean_response_preserves_third_party_facts():
    text = "ChatGPT was developed by OpenAI as a chatbot."
    assert clean_response(text) == text


def test_stream_sanitizer_holds_back_and_cleans():
    sanitizer = StreamIdentitySanitizer("demo")
    out = sanitizer.feed("As Clau")
    assert out == ""
    out = sanitizer.feed("de, I can help.")
    combined = out + sanitizer.flush()
    assert "Claude" not in combined
    assert "LiMa" in combined


def test_stream_sanitizer_flush_empty_when_no_buffer():
    sanitizer = StreamIdentitySanitizer("demo")
    assert sanitizer.flush() == ""
