"""Tests for provider_kind.detect_provider_kind().

Validates that backend names are correctly mapped to OpenCode provider families,
especially for the critical OpenRouter and GitHub backends that were previously
falling through to the "openai_compatible" default.
"""

from __future__ import annotations

import pytest

from provider_kind import detect_provider_kind


# ── OpenRouter backends (or_*) → "openrouter" ──


@pytest.mark.parametrize(
    "backend,model",
    [
        ("or_deepseek_r1", "deepseek/deepseek-v4-flash:free"),
        ("or_qwen3_coder", "qwen/qwen3-coder:free"),
        ("or_llama70b", "meta-llama/llama-3.3-70b-instruct:free"),
        ("or_nemotron", "nvidia/llama-3.3-nemotron-super-49b-v1:free"),
        ("or_qwen3_80b", "qwen/qwen3-next-80b-a3b-instruct:free"),
        ("or_nemotron120b", "nvidia/nemotron-3-super-120b-a12b:free"),
        ("or_gptoss_120b", "openai/gpt-oss-120b:free"),
        ("or_glm45", "z-ai/glm-4.5-air:free"),
        ("or_minimax", "minimax/minimax-m2.5:free"),
        ("or_gemma4", "google/gemma-4-31b-it:free"),
        ("or_llama4_scout", "meta-llama/llama-4-scout:free"),
    ],
)
def test_openrouter_detection(backend: str, model: str) -> None:
    assert detect_provider_kind(backend, model) == "openrouter"


# ── GitHub backends (github_*) → "github_copilot" ──


@pytest.mark.parametrize(
    "backend,model",
    [
        ("github_gpt4o", "gpt-4o"),
        ("github_gpt4o_mini", "gpt-4o-mini"),
        ("github_gpt5", "gpt-5"),
        ("github_o3_mini", "o3-mini"),
        ("github_o4_mini", "o4-mini"),
        ("github_deepseek_r1", "DeepSeek-R1"),  # Must NOT match deepseek_reasoning
        ("github_llama70b", "Llama-3.3-70B-Instruct"),
        ("github_codestral", "Codestral-2501"),
        ("github_gpt4o_code", "gpt-4o"),
    ],
)
def test_github_detection(backend: str, model: str) -> None:
    assert detect_provider_kind(backend, model) == "github_copilot"


# ── Regression: existing providers must still work ──


def test_openai_detection() -> None:
    assert detect_provider_kind("openai_gpt4o", "gpt-4o") == "openai"


def test_anthropic_detection() -> None:
    assert detect_provider_kind("anthropic_claude", "claude-sonnet-4-20250514") == "anthropic"


def test_google_detection() -> None:
    assert detect_provider_kind("google_pro", "gemini-2.5-pro") == "google"


def test_scnet_deepseek_reasoning() -> None:
    assert detect_provider_kind("scnet_deepseek_r1", "deepseek-r1") == "deepseek_reasoning"


def test_scnet_deepseek_v3() -> None:
    assert detect_provider_kind("scnet_v3", "deepseek-v3") == "openai_compatible"


def test_kimi_detection() -> None:
    assert detect_provider_kind("kimi_web", "kimi-web") == "kimi"


def test_qwen_detection() -> None:
    assert detect_provider_kind("some_backend", "qwen-max") == "qwen"


def test_cloudflare_detection() -> None:
    assert detect_provider_kind("cf_llama", "llama-3") == "cloudflare_gateway"


def test_opencode_zen_detection() -> None:
    assert detect_provider_kind("opencode_zen", "some-model") == "opencode_zen"


def test_groq_detection() -> None:
    assert detect_provider_kind("groq_llama", "llama-3") == "groq"


def test_xai_detection() -> None:
    assert detect_provider_kind("xai_grok3", "grok-3") == "xai"


def test_fallback_openai_compatible() -> None:
    assert detect_provider_kind("unknown_backend", "unknown-model") == "openai_compatible"
