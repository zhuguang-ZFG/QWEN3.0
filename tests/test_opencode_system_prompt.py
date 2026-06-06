"""Tests for opencode_system_prompt.py — model family prompt routing."""


from opencode_system_prompt import (
    enhance_system_prompt,
    get_model_family_hint,
    resolve_prompt_template,
    resolve_provider_kind,
)


class TestResolvePromptTemplate:
    """resolve_prompt_template() tests."""

    # ── Beast models ──

    def test_gpt4(self):
        assert resolve_prompt_template("gpt-4o") == "beast"

    def test_gpt4_turbo(self):
        assert resolve_prompt_template("gpt-4-turbo") == "beast"

    def test_o1(self):
        assert resolve_prompt_template("o1-preview") == "beast"

    def test_o3(self):
        assert resolve_prompt_template("o3-mini") == "beast"

    def test_o4(self):
        assert resolve_prompt_template("o4-mini") == "beast"

    def test_gpt5(self):
        assert resolve_prompt_template("gpt-5") == "beast"

    # ── Codex ──

    def test_codex(self):
        assert resolve_prompt_template("codex-mini", "codex") == "codex"

    # ── Gemini ──

    def test_gemini_flash(self):
        assert resolve_prompt_template("gemini-2.5-flash") == "gemini"

    def test_gemini_pro(self):
        assert resolve_prompt_template("gemini-2.5-pro") == "gemini"

    def test_gemini_backend(self):
        assert resolve_prompt_template("some-model", "google_gemini") == "gemini"

    # ── Anthropic ──

    def test_claude_sonnet(self):
        assert resolve_prompt_template("claude-sonnet-4-20250514") == "anthropic"

    def test_claude_haiku(self):
        assert resolve_prompt_template("claude-3-5-haiku") == "anthropic"

    def test_anthropic_backend(self):
        assert resolve_prompt_template("some-model", "anthropic_claude") == "anthropic"

    # ── Trinity ──

    def test_trinity(self):
        assert resolve_prompt_template("trinity-large") == "trinity"

    # ── Kimi ──

    def test_kimi(self):
        assert resolve_prompt_template("kimi-latest") == "kimi"

    def test_moonshot(self):
        assert resolve_prompt_template("moonshot-v1") == "kimi"

    # ── DeepSeek ──

    def test_deepseek(self):
        assert resolve_prompt_template("deepseek-v3") == "deepseek"

    def test_deepseek_backend(self):
        assert resolve_prompt_template("some-model", "scnet_ds_flash") == "deepseek"

    # ── Qwen ──

    def test_qwen(self):
        assert resolve_prompt_template("qwen-coder-32b") == "qwen"

    # ── Llama ──

    def test_llama(self):
        assert resolve_prompt_template("llama-4-405b") == "llama"

    # ── GPT (non-beast) ──

    def test_gpt35(self):
        assert resolve_prompt_template("gpt-3.5-turbo") == "gpt"

    # ── Default ──

    def test_unknown(self):
        assert resolve_prompt_template("some-unknown-model") == "default"

    def test_empty(self):
        assert resolve_prompt_template("") == "default"


class TestGetModelFamilyHint:
    """get_model_family_hint() tests."""

    def test_beast_hint(self):
        hint = get_model_family_hint("gpt-4o")
        assert "high-capability" in hint or "reasoning" in hint.lower()

    def test_anthropic_hint(self):
        hint = get_model_family_hint("claude-sonnet-4-20250514")
        assert "thinking" in hint.lower() or "structured" in hint.lower()

    def test_gemini_hint(self):
        hint = get_model_family_hint("gemini-2.5-flash")
        assert "multimodal" in hint.lower() or "context" in hint.lower()

    def test_default_hint(self):
        hint = get_model_family_hint("unknown-model")
        assert hint == ""


class TestEnhanceSystemPrompt:
    """enhance_system_prompt() tests."""

    def test_basic_enhancement(self):
        result = enhance_system_prompt("You are a helper.", "gpt-4o")
        assert "You are a helper." in result
        assert "Model Optimization" in result

    def test_no_hint_for_unknown(self):
        result = enhance_system_prompt("base prompt", "unknown-model")
        assert result == "base prompt"

    def test_environment_injection(self):
        env = {"os": "Windows 11", "cwd": "/home/user", "shell": "bash"}
        result = enhance_system_prompt("prompt", "gpt-4o", environment_info=env)
        assert "Windows 11" in result
        assert "/home/user" in result
        assert "bash" in result

    def test_empty_system_prompt(self):
        result = enhance_system_prompt("", "gpt-4o")
        assert "Model Optimization" in result

    def test_no_environment(self):
        result = enhance_system_prompt("prompt", "unknown-model")
        assert "Environment" not in result

    def test_partial_environment(self):
        result = enhance_system_prompt("prompt", "gpt-4o", environment_info={"os": "Linux"})
        assert "Linux" in result


class TestResolveProviderKind:
    """resolve_provider_kind() tests."""

    def test_openai(self):
        assert resolve_provider_kind("gpt-4o") == "openai"

    def test_anthropic(self):
        assert resolve_provider_kind("claude-sonnet-4-20250514") == "anthropic"

    def test_google(self):
        assert resolve_provider_kind("gemini-2.5-flash") == "google"

    def test_kimi(self):
        assert resolve_provider_kind("kimi-latest") == "kimi"

    def test_deepseek(self):
        assert resolve_provider_kind("deepseek-v3") == "deepseek"

    def test_unknown(self):
        assert resolve_provider_kind("some-model") == "unknown"

    def test_backend_name_helps(self):
        assert resolve_provider_kind("model-x", "anthropic_backend") == "anthropic"
