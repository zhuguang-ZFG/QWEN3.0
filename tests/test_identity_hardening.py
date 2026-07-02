"""Identity guard and response cleaner hardening tests."""

import brand_config
from response_cleaner import (
    StreamIdentitySanitizer,
    apply_identity_cleaning,
    clean_response,
)
import identity_guard


def test_clean_response_as_claude_intro():
    result = clean_response("As Claude, I can help with code.")
    assert "Claude" not in result
    assert "LiMa" in result


def test_clean_response_this_is_gemini():
    result = clean_response("This is Gemini speaking. How can I help?")
    assert "Gemini" not in result
    assert "LiMa" in result


def test_clean_response_claude_here():
    result = clean_response("Claude here! Ask me anything.")
    assert "Claude" not in result


def test_clean_response_preserves_third_party_facts():
    text = "ChatGPT was developed by OpenAI as a chatbot."
    assert clean_response(text) == text


def test_filter_identity_leak_uses_english_for_english_response():
    leaked = "I am Claude, an AI assistant made by Anthropic."
    result = identity_guard.filter_identity_leak(leaked)
    assert "Claude" not in result
    assert "Anthropic" not in result
    assert "LiMa" in result
    assert "Technology" not in result or "DongLiCao" in result


def test_filter_identity_leak_uses_chinese_for_chinese_response():
    leaked = "我是 Claude，由 Anthropic 开发的 AI 助手。"
    result = identity_guard.filter_identity_leak(leaked)
    assert "Claude" not in result
    assert "Anthropic" not in result
    assert "LiMa" in result


def test_apply_identity_cleaning_partial_replace():
    result = apply_identity_cleaning("As Claude, I can help with Python.")
    assert "Claude" not in result
    assert "Python" in result


def test_filter_identity_leak_falls_back_to_short_english():
    leaked = "As Claude, I must tell you I am Claude from Anthropic."
    result = identity_guard.filter_identity_leak(leaked, prefer_language="en")
    assert "Claude" not in result
    assert "Anthropic" not in result
    result = apply_identity_cleaning("As Claude, I can help with Python.")
    assert "Claude" not in result
    assert "Python" in result


def test_guest_identity_answer_is_conservative():
    answer = identity_guard.detect_identity_question("你是谁", channel_role="guest")
    assert answer is not None
    assert "天气" not in answer
    assert "股票" not in answer
    assert "访客" in answer or "guest" in answer.lower() or "公开" in answer


def test_guest_capability_answer_no_overpromise():
    answer = identity_guard.detect_identity_question("你能做什么", channel_role="guest")
    assert answer is not None
    assert "二维码" not in answer
    assert "语音" not in answer


def test_owner_capability_answer_keeps_full_list():
    answer = identity_guard.detect_identity_question("你能做什么", channel_role="default")
    assert answer is not None
    assert "编程" in answer or "Programming" in answer


def test_stream_sanitizer_cleans_cross_chunk_identity():
    sanitizer = StreamIdentitySanitizer("demo")
    out = sanitizer.feed("As Clau")
    assert out == ""
    out = sanitizer.feed("de, I can help.")
    assert "Claude" not in (out + sanitizer.flush())
    combined = out + sanitizer.flush()
    if combined:
        assert "Claude" not in combined


def test_identity_answers_use_brand_config():
    """Identity/capability answers should be built from brand_config constants."""
    assert brand_config.COMPANY_NAME_CN in identity_guard.IDENTITY_ANSWER_CN
    assert brand_config.COMPANY_NAME_EN in identity_guard.IDENTITY_ANSWER_EN
    assert brand_config.COMPANY_SHORT_CN in identity_guard.SHORT_LEAK_REPLACEMENT_CN
    assert brand_config.COMPANY_NAME_EN in identity_guard.SHORT_LEAK_REPLACEMENT_EN
    assert brand_config.PUBLIC_MODEL_NAME in identity_guard.IDENTITY_ANSWER_CN
    assert brand_config.PUBLIC_MODEL_NAME in identity_guard.IDENTITY_ANSWER_EN
    assert brand_config.PUBLIC_MODEL_NAME in identity_guard.CAPABILITY_ANSWER_CN
    assert brand_config.PUBLIC_MODEL_NAME in identity_guard.CAPABILITY_ANSWER_EN
    assert brand_config.PUBLIC_MODEL_NAME in identity_guard.IDENTITY_ANSWER_GUEST_CN
    assert brand_config.PUBLIC_MODEL_NAME in identity_guard.IDENTITY_ANSWER_GUEST_EN
    assert brand_config.PUBLIC_MODEL_NAME in identity_guard.CAPABILITY_ANSWER_GUEST_CN
    assert brand_config.PUBLIC_MODEL_NAME in identity_guard.CAPABILITY_ANSWER_GUEST_EN
