"""Tests for opencode_prompt_cache.py — prompt caching marker injection."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from opencode_prompt_cache import (
    apply_prompt_caching,
    should_apply_caching,
    _deep_merge,
)


class TestShouldApplyCaching:
    def test_anthropic(self):
        assert should_apply_caching("anthropic_claude", "claude-3.5-sonnet", "anthropic")

    def test_openrouter(self):
        assert should_apply_caching("or_anthropic", "claude-3-opus", "openrouter")

    def test_bedrock(self):
        assert should_apply_caching("bedrock_us", "claude-3", "bedrock")

    def test_openai_no_caching(self):
        assert not should_apply_caching("openai", "gpt-4o", "openai")

    def test_ai_gateway_skip(self):
        assert not should_apply_caching("ai_gateway", "any-model", "ai_gateway")

    def test_alibaba(self):
        assert should_apply_caching("alibaba_dashscope", "qwen-max", "alibaba")


class TestApplyPromptCaching:
    def test_anthropic_system_messages(self):
        msgs = [
            {"role": "system", "content": "You are helpful"},
            {"role": "system", "content": "Additional context"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
        ]
        result = apply_prompt_caching(msgs, "anthropic", "claude-3.5-sonnet", "anthropic")
        # System messages should get providerOptions
        assert "providerOptions" in result[0]
        assert "anthropic" in result[0]["providerOptions"]
        assert result[0]["providerOptions"]["anthropic"]["cacheControl"]["type"] == "ephemeral"
        # Non-system last 2 messages should also get caching
        assert "providerOptions" in result[-1]

    def test_bedrock_cache_point(self):
        msgs = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "Hello"},
        ]
        result = apply_prompt_caching(msgs, "bedrock_us", "claude-3", "bedrock")
        assert "providerOptions" in result[0]
        assert "bedrock" in result[0]["providerOptions"]
        assert result[0]["providerOptions"]["bedrock"]["cachePoint"]["type"] == "default"

    def test_openai_no_caching(self):
        msgs = [
            {"role": "user", "content": "Hello"},
        ]
        result = apply_prompt_caching(msgs, "openai", "gpt-4o", "openai")
        # No caching for openai
        assert "providerOptions" not in result[0]

    def test_array_content(self):
        msgs = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Hello"},
                    {"type": "text", "text": "World"},
                ],
            },
        ]
        result = apply_prompt_caching(msgs, "anthropic", "claude-3", "anthropic")
        # Cache should be on the last content part
        last_part = result[0]["content"][-1]
        assert "providerOptions" in last_part

    def test_original_not_mutated(self):
        msgs = [{"role": "user", "content": "Hello"}]
        original = list(msgs)
        apply_prompt_caching(msgs, "anthropic", "claude-3", "anthropic")
        assert msgs == original

    def test_empty_messages(self):
        result = apply_prompt_caching([], "anthropic", "claude-3", "anthropic")
        assert result == []


class TestDeepMerge:
    def test_simple(self):
        assert _deep_merge({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}

    def test_override(self):
        assert _deep_merge({"a": 1}, {"a": 2}) == {"a": 2}

    def test_nested(self):
        base = {"a": {"b": 1, "c": 2}}
        override = {"a": {"c": 3, "d": 4}}
        result = _deep_merge(base, override)
        assert result == {"a": {"b": 1, "c": 3, "d": 4}}
