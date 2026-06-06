"""Tests for opencode_provider_namespace.py — namespace key mapping."""


from opencode_provider_namespace import (
    build_provider_options_for_body,
    resolve_provider_namespace_key,
    wrap_provider_options,
)


class TestResolveProviderNamespaceKey:
    """resolve_provider_namespace_key() tests."""

    def test_openai(self):
        assert resolve_provider_namespace_key("openai") == ["openai"]

    def test_anthropic(self):
        assert resolve_provider_namespace_key("anthropic") == ["anthropic"]

    def test_google(self):
        assert resolve_provider_namespace_key("google") == ["google"]

    def test_azure_dual_keys(self):
        keys = resolve_provider_namespace_key("azure")
        assert keys == ["openai", "azure"]

    def test_bedrock(self):
        assert resolve_provider_namespace_key("bedrock") == ["bedrock"]

    def test_openrouter(self):
        assert resolve_provider_namespace_key("openrouter") == ["openrouter"]

    def test_gateway(self):
        keys = resolve_provider_namespace_key("ai_gateway", "gw_openai_gpt4")
        assert "gateway" in keys
        assert "openai" in keys

    def test_openai_compatible(self):
        keys = resolve_provider_namespace_key("openai_compatible", "scnet_ds_flash")
        assert len(keys) == 1
        assert keys[0] == "deepseek"

    def test_unknown_fallback(self):
        keys = resolve_provider_namespace_key("unknown_provider")
        assert keys == ["unknown_provider"]


class TestWrapProviderOptions:
    """wrap_provider_options() tests."""

    def test_single_key(self):
        opts = {"store": False, "reasoningEffort": "high"}
        result = wrap_provider_options(opts, ["openai"])
        assert result == {"openai": {"store": False, "reasoningEffort": "high"}}

    def test_dual_keys(self):
        opts = {"store": False}
        result = wrap_provider_options(opts, ["openai", "azure"])
        assert "openai" in result
        assert "azure" in result
        assert result["openai"] == {"store": False}
        assert result["azure"] == {"store": False}

    def test_empty_options(self):
        assert wrap_provider_options({}, ["openai"]) == {}

    def test_empty_keys(self):
        assert wrap_provider_options({"store": False}, []) == {}


class TestBuildProviderOptionsForBody:
    """build_provider_options_for_body() tests."""

    def test_openai_session(self):
        opts = {"store": False, "promptCacheKey": "sess-1"}
        result = build_provider_options_for_body(opts, "openai", "openai_gpt5", "gpt-5")
        assert "openai" in result
        assert result["openai"]["store"] is False

    def test_azure_session(self):
        opts = {"store": False, "promptCacheKey": "sess-1"}
        result = build_provider_options_for_body(opts, "azure", "azure_gpt5", "gpt-5")
        assert "openai" in result
        assert "azure" in result

    def test_empty_session_options(self):
        result = build_provider_options_for_body({}, "openai")
        assert result == {}
