"""Tests for model_resolver.resolve_backend()."""

import os

# Ensure feature gate is ON for tests (default behavior)
os.environ.setdefault("LIMA_ALLOW_MODEL_OVERRIDE", "true")

from model_resolver import resolve_backend

# ── Exact backend name matching ──

def test_exact_backend_name():
    """Client passes a known LiMa backend name directly."""
    result = resolve_backend("github_gpt4o")
    assert result == "github_gpt4o"


def test_exact_backend_name_scnet():
    result = resolve_backend("scnet_ds_pro")
    assert result == "scnet_ds_pro"


def test_exact_backend_name_longcat():
    result = resolve_backend("longcat")
    assert result == "longcat"


def test_exact_backend_name_kimi():
    result = resolve_backend("kimi")
    assert result == "kimi"


# ── Alias matching ──

def test_alias_gpt4o():
    result = resolve_backend("gpt-4o")
    assert result == "github_gpt4o"


def test_alias_gpt4o_mini():
    result = resolve_backend("gpt-4o-mini")
    assert result == "github_gpt4o_mini"


def test_alias_deepseek_v3():
    result = resolve_backend("deepseek-v3")
    assert result == "scnet_ds_pro"


def test_alias_deepseek_v4_flash():
    result = resolve_backend("deepseek-v4-flash")
    assert result == "scnet_ds_flash"


def test_alias_qwen_max():
    result = resolve_backend("qwen-max")
    assert result == "scnet_qwen235b"


def test_alias_claude_opus():
    result = resolve_backend("claude-opus")
    assert result == "longcat"


def test_alias_claude_3_opus():
    result = resolve_backend("claude-3-opus")
    assert result == "longcat"


def test_alias_llama_70b():
    result = resolve_backend("llama-3.3-70b")
    assert result == "groq_llama70b"


def test_alias_gemini_flash():
    result = resolve_backend("gemini-flash")
    assert result == "google_flash"


def test_alias_mistral_large():
    result = resolve_backend("mistral-large")
    assert result == "mistral_large"


def test_alias_codestral():
    result = resolve_backend("codestral")
    assert result == "mistral_codestral"


def test_alias_mimo():
    result = resolve_backend("mimo")
    assert result == "mimo_web"


def test_alias_kimi_direct():
    result = resolve_backend("kimi")
    assert result == "kimi"


def test_alias_gpt_oss_120b():
    result = resolve_backend("gpt-oss-120b")
    assert result == "cf_gptoss_120b"


# ── Auto-routing fallback ──

def test_empty_string_returns_none():
    assert resolve_backend("") is None


def test_none_like_returns_none():
    assert resolve_backend("auto") is None
    assert resolve_backend("default") is None
    assert resolve_backend("lima-1.3") is None


def test_unknown_model_returns_none():
    assert resolve_backend("totally-unknown-model-xyz") is None


def test_nonexistent_backend_returns_none():
    """A name that looks like a backend but doesn't exist."""
    assert resolve_backend("github_nonexistent_model") is None


# ── Feature gate ──

def test_feature_gate_off():
    """When LIMA_ALLOW_MODEL_OVERRIDE=false, all models fall through."""
    import model_resolver as mr
    original = mr._ALLOW_MODEL_OVERRIDE
    try:
        mr._ALLOW_MODEL_OVERRIDE = False
        assert resolve_backend("gpt-4o") is None
        assert resolve_backend("github_gpt4o") is None
    finally:
        mr._ALLOW_MODEL_OVERRIDE = original


# ── Edge cases ──

def test_case_sensitivity():
    """Model names are case-sensitive."""
    assert resolve_backend("GPT-4O") is None
    assert resolve_backend("Gpt-4o") is None


def test_alias_pointing_to_missing_backend():
    """If an alias target doesn't exist in BACKENDS, return None."""
    # 'default' maps to None in MODEL_ALIASES, handled by the None check
    assert resolve_backend("default") is None
