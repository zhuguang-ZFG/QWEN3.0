"""M-OC3 Round 3 regression tests.

Covers reasoning_variants, session_options, error adapter
(parse_stream_error / parse_api_error), and message normalizer
(DeepSeek reasoning injection + interleaved extraction).
"""

import json

import pytest

# ── reasoning_variants ────────────────────────────────────────────────────
from reasoning_variants import (
    apply_variant,
    compute_variants,
    list_efforts,
    openai_reasoning_efforts,
)


class TestReasoningVariants:
    def test_openai_gpt51_efforts(self):
        """GPT-5.1 supports none/low/medium/high (no xhigh)."""
        efforts = openai_reasoning_efforts("gpt-5.1", "2025-11-14")
        assert "none" in efforts
        assert "low" in efforts
        assert "medium" in efforts
        assert "high" in efforts
        assert "xhigh" not in efforts

    def test_openai_gpt52_efforts(self):
        """GPT-5.2 supports none/low/medium/high/xhigh."""
        efforts = openai_reasoning_efforts("gpt-5.2", "2025-12-05")
        assert "xhigh" in efforts
        assert "none" in efforts

    def test_gpt5_pro_efforts(self):
        """GPT-5-pro only supports high."""
        efforts = openai_reasoning_efforts("gpt-5-pro", "")
        assert efforts == ["high"]

    def test_gpt5_chat_efforts(self):
        """GPT-5-chat only supports medium."""
        efforts = openai_reasoning_efforts("gpt-5.1-chat", "")
        assert efforts == ["medium"]

    def test_gpt5_codex_xhigh(self):
        """GPT-5-codex-max supports low/medium/high/xhigh."""
        efforts = openai_reasoning_efforts("gpt-5-codex-max", "")
        assert "xhigh" in efforts
        assert "low" in efforts

    def test_scnet_ds_v4_variants(self):
        """SCNet DeepSeek V4 gets low/medium/high/max."""
        efforts = list_efforts("scnet_ds_flash", "deepseek-v4-flash-free")
        assert "low" in efforts
        assert "high" in efforts
        assert "max" in efforts

    def test_scnet_apply_low(self):
        """apply_variant translates low effort to {reasoningEffort: low}."""
        opts = apply_variant("scnet_ds_flash", "deepseek-v4-flash", "low")
        assert opts == {"reasoningEffort": "low"}

    def test_anthropic_sonnet_46_variants(self):
        """Claude Sonnet 4.6 gets adaptive thinking with low/medium/high/max."""
        efforts = list_efforts("anthropic_sonnet46", "sonnet-4.6-20250714")
        assert "low" in efforts
        assert "high" in efforts
        assert "max" in efforts
        opts = apply_variant("anthropic_sonnet46", "sonnet-4.6-20250714", "high")
        assert opts.get("thinking", {}).get("type") == "adaptive"

    def test_google_gemini3_variants(self):
        """Gemini 3 flash gets minimal/low/medium/high levels."""
        efforts = list_efforts("google_gemini3", "gemini-3-flash")
        assert "minimal" in efforts
        assert "high" in efforts

    def test_grok3_mini_variants(self):
        """Grok 3 Mini returns low/high reasoningEffort."""
        variants = compute_variants("xai_grok3", "grok-3-mini", provider_kind="xai")
        assert "low" in variants
        assert "high" in variants
        assert variants["low"] == {"reasoningEffort": "low"}

    def test_unsupported_model_returns_empty(self):
        """Non-reasoning models return empty variants."""
        variants = compute_variants("some_backend", "mistral-small", reasoning_capable=False)
        assert variants == {}

    def test_mistral_reasoning(self):
        """Mistral medium-3.5 supports high effort."""
        variants = compute_variants("mistral_medium", "mistral-medium-3.5", provider_kind="mistral")
        assert "high" in variants
        assert variants["high"] == {"reasoningEffort": "high"}


# ── session_options ───────────────────────────────────────────────────────

from session_options import resolve_session_options


class TestSessionOptions:
    def test_openai_store_false(self):
        """OpenAI provider sets store=false."""
        opts = resolve_session_options("openai", "gpt-5.1", provider_kind="openai")
        assert opts.get("store") is False

    def test_openai_session_cache_key(self):
        """OpenAI provider sets promptCacheKey with session_id."""
        opts = resolve_session_options("openai", "gpt-5.1", provider_kind="openai", session_id="s1")
        assert opts.get("promptCacheKey") == "s1"

    def test_anthropic_non_claude_tool_streaming(self):
        """Non-Claude Anthropic backend sets toolStreaming=false."""
        opts = resolve_session_options("anthropic_gemini", "gemini-flash", provider_kind="anthropic")
        assert opts.get("toolStreaming") is False

    def test_claude_anthropic_no_tool_streaming(self):
        """Claude models via Anthropic do NOT set toolStreaming=false."""
        opts = resolve_session_options("anthropic", "claude-sonnet-4", provider_kind="anthropic")
        assert "toolStreaming" not in opts

    def test_gpt5_default_reasoning(self):
        """GPT-5 gets reasoningEffort=medium, textVerbosity=low."""
        opts = resolve_session_options("openai", "gpt-5.1", provider_kind="openai")
        assert opts.get("reasoningEffort") == "medium"
        assert opts.get("textVerbosity") == "low"
        assert opts.get("reasoningSummary") == "auto"

    def test_google_reasoning_capable(self):
        """Google reasoning models get thinkingConfig."""
        opts = resolve_session_options("google_gemini", "gemini-3-pro", provider_kind="google", reasoning_capable=True)
        assert "thinkingConfig" in opts
        assert opts["thinkingConfig"].get("includeThoughts") is True

    def test_dashscope_enable_thinking(self):
        """DashScope reasoning models get enable_thinking."""
        opts = resolve_session_options(
            "alibaba_qwen", "qwq-32b", reasoning_capable=True
        )
        assert opts.get("enable_thinking") is True


# ── error adapter ─────────────────────────────────────────────────────────

from opencode_error_adapter import (
    detect_context_overflow,
    parse_api_error,
    parse_stream_error,
)


class TestParseStreamError:
    def test_insufficient_quota(self):
        r = parse_stream_error(json.dumps({"type": "error", "error": {"code": "insufficient_quota"}}))
        assert r is not None
        assert r["type"] == "api_error"
        assert r["isRetryable"] is False

    def test_server_overloaded(self):
        r = parse_stream_error(json.dumps({"type": "error", "error": {"code": "server_is_overloaded"}}))
        assert r is not None
        assert r["type"] == "api_error"
        assert r["isRetryable"] is True

    def test_context_length_exceeded(self):
        r = parse_stream_error(json.dumps({"type": "error", "error": {"code": "context_length_exceeded"}}))
        assert r is not None
        assert r["type"] == "context_overflow"

    def test_non_error_event(self):
        r = parse_stream_error(json.dumps({"type": "message", "content": "hello"}))
        assert r is None

    def test_bad_json(self):
        r = parse_stream_error("not json")
        assert r is None

    def test_invalid_prompt(self):
        r = parse_stream_error(json.dumps({"type": "error", "error": {"code": "invalid_prompt", "message": "bad input"}}))
        assert r is not None
        assert r["isRetryable"] is False
        assert "bad input" in r["message"]

    def test_nested_message_json(self):
        inner = json.dumps({"type": "error", "error": {"code": "server_error"}})
        r = parse_stream_error(json.dumps({"type": "error", "message": inner}))
        assert r is not None
        assert r["isRetryable"] is True


class TestParseAPIError:
    def test_context_overflow_detected(self):
        r = parse_api_error(
            {"message": "test"},
            status_code=400,
            response_body=json.dumps({"error": {"code": "context_length_exceeded"}}),
            url="http://test/v1",
        )
        assert r["type"] == "context_overflow"

    def test_api_error_structured(self):
        r = parse_api_error(
            {"message": "Rate limited", "isRetryable": True},
            status_code=429,
            response_headers={"retry-after": "30"},
            url="http://test/v1",
        )
        assert r["type"] == "api_error"
        assert r["isRetryable"] is True
        assert r["statusCode"] == 429
        assert r["responseHeaders"]["retry-after"] == "30"
        assert r["metadata"]["url"] == "http://test/v1"

    def test_overflow_by_status_code(self):
        """HTTP 413 is detected as overflow."""
        assert detect_context_overflow("random error", status_code=413) is True


# ── message normalizer ────────────────────────────────────────────────────

from opencode_message_normalizer import (
    extract_interleaved_reasoning,
    inject_deepseek_reasoning,
    normalize_messages,
)


class TestDeepSeekNormalizer:
    def test_inject_reasoning_to_assistant(self):
        """Assistant message without reasoning gets empty reasoning injected."""
        msgs = [{"role": "assistant", "content": "Hello world"}]
        result = inject_deepseek_reasoning(msgs)
        parts = result[0]["content"]
        assert any(p.get("type") == "reasoning" for p in parts)

    def test_skip_if_already_has_reasoning(self):
        """Assistant message with existing reasoning is unchanged."""
        msgs = [{"role": "assistant", "content": [{"type": "reasoning", "text": "thinking..."}, {"type": "text", "text": "answer"}]}]
        result = inject_deepseek_reasoning(msgs)
        assert len(result[0]["content"]) == 2

    def test_skip_non_assistant(self):
        """Non-assistant messages pass through unchanged."""
        msgs = [{"role": "user", "content": "hello"}]
        result = inject_deepseek_reasoning(msgs)
        assert result == msgs

    def test_extract_interleaved(self):
        """Reasoning parts are extracted to providerOptions.openaiCompatible."""
        msgs = [{
            "role": "assistant",
            "content": [
                {"type": "reasoning", "text": "Let me think..."},
                {"type": "text", "text": "Here is the answer."},
            ],
        }]
        result = extract_interleaved_reasoning(msgs)
        opts = result[0].get("providerOptions", {}).get("openaiCompatible", {})
        assert opts.get("reasoning_content") == "Let me think..."
        # Content should only have text part
        assert len(result[0]["content"]) == 1
        assert result[0]["content"][0]["type"] == "text"

    def test_normalize_deepseek_pipeline(self):
        """Full normalize_messages pipeline for DeepSeek backend.
        Injected reasoning gets extracted to providerOptions."""
        msgs = [{"role": "assistant", "content": "Hello"}]
        result = normalize_messages(msgs, "scnet_deepseek")
        opts = result[0].get("providerOptions", {}).get("openaiCompatible", {})
        assert "reasoning_content" in opts

    def test_normalize_non_deepseek_untouched(self):
        """Non-DeepSeek backends do not inject reasoning."""
        msgs = [{"role": "assistant", "content": "Hello"}]
        result = normalize_messages(msgs, "openai_gpt4")
        assert result[0]["content"] == "Hello"


# ── integration: no regressions in existing normalize path ─────────────────

class TestNoRegression:
    def test_normalize_surrogate_cleanup(self):
        msgs = [{"role": "user", "content": "bad \ud800 char"}]
        result = normalize_messages(msgs, "anthropic")
        assert "\ud800" not in result[0]["content"]

    def test_normalize_empty_message_filter(self):
        msgs = [{"role": "assistant", "content": ""}]
        result = normalize_messages(msgs, "anthropic")
        assert len(result) == 0

    def test_normalize_toolcall_id_scrub(self):
        msgs = [{"role": "assistant", "content": [{"type": "tool_use", "toolCallId": "bad!@#id"}]}]
        result = normalize_messages(msgs, "anthropic")
        tid = result[0]["content"][0]["toolCallId"]
        assert "!" not in tid
        assert "@" not in tid
