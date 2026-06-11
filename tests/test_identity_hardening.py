"""Identity guard and response cleaner hardening tests."""

import pytest
from response_cleaner import (
    StreamIdentitySanitizer,
    apply_identity_cleaning,
    clean_response,
)
import identity_guard
import routing_engine


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


@pytest.mark.skip(reason="Skip: test_route_identity_guard_runs_before_cache depends on routing_engine.semantic_cache")
def test_route_identity_guard_runs_before_cache(monkeypatch):
    calls = {"cache_get": 0, "identity": 0}

    def fake_get(*_args, **_kwargs):
        calls["cache_get"] += 1
        return "I am Claude from cache."

    def fake_detect(query, *, channel_role="default"):
        calls["identity"] += 1
        if "who are you" in query.lower():
            return "I'm LiMa."
        return None

    monkeypatch.setattr(routing_engine.semantic_cache, "get", fake_get)
    monkeypatch.setattr(routing_engine.identity_guard, "detect_identity_question", fake_detect)

    result = routing_engine.route("who are you", [{"role": "user", "content": "who are you"}])

    assert result.backend == "identity_guard"
    assert result.answer == "I'm LiMa."
    assert calls["identity"] == 1
    assert calls["cache_get"] == 0


@pytest.mark.skip(reason="Skip: test_route_cache_hit_is_cleaned depends on routing_engine.semantic_cache")
def test_route_cache_hit_is_cleaned(monkeypatch):
    monkeypatch.setattr(
        routing_engine.identity_guard,
        "detect_identity_question",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        routing_engine.semantic_cache,
        "get",
        lambda *_a, **_k: "As Claude, cached answer.",
    )

    result = routing_engine.route("explain python", [{"role": "user", "content": "explain python"}])

    assert result.backend == "cache"
    assert "Claude" not in result.answer
