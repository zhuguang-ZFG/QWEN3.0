"""Tests for Bedrock reasoningConfig in reasoning_variants.py (Round 4)."""


from reasoning_variants import apply_variant, compute_variants, list_efforts


class TestBedrockReasoningConfig:
    """Test Bedrock-specific reasoningConfig format (transform.ts:855-900)."""

    def test_nova_model_returns_widely_supported(self):
        variants = compute_variants("bedrock_nova", "amazon.nova-pro-v1:0", "bedrock")
        assert "low" in variants
        assert "medium" in variants
        assert "high" in variants
        for effort, opts in variants.items():
            assert "reasoningConfig" in opts
            rc = opts["reasoningConfig"]
            assert rc["type"] == "enabled"
            assert rc["maxReasoningEffort"] == effort

    def test_claude_on_bedrock_budget_tokens(self):
        variants = compute_variants("bedrock_claude", "anthropic.claude-3-sonnet", "bedrock")
        assert "high" in variants
        assert "max" in variants
        assert variants["high"]["reasoningConfig"]["budgetTokens"] == 16000
        assert variants["max"]["reasoningConfig"]["budgetTokens"] == 31999
        assert variants["high"]["reasoningConfig"]["type"] == "enabled"

    def test_opus_46_adaptive_on_bedrock(self):
        variants = compute_variants("bedrock", "anthropic.claude-opus-4-6", "bedrock")
        assert "low" in variants
        assert "high" in variants
        assert "max" in variants
        for effort, opts in variants.items():
            rc = opts["reasoningConfig"]
            assert rc["type"] == "adaptive"
            assert rc["maxReasoningEffort"] == effort

    def test_sonnet_46_adaptive_on_bedrock(self):
        variants = compute_variants("bedrock", "anthropic.claude-sonnet-4-6", "bedrock")
        efforts = list_efforts("bedrock", "anthropic.claude-sonnet-4-6", "bedrock")
        assert "low" in efforts
        assert "high" in efforts

    def test_opus_47_display_summarized(self):
        variants = compute_variants("bedrock", "anthropic.claude-opus-4-7", "bedrock")
        for effort, opts in variants.items():
            rc = opts["reasoningConfig"]
            assert rc["type"] == "adaptive"
            assert rc.get("display") == "summarized"

    def test_apply_variant_bedrock_nova(self):
        result = apply_variant("bedrock", "amazon.nova-lite-v1:0", "high", "bedrock")
        assert "reasoningConfig" in result
        assert result["reasoningConfig"]["maxReasoningEffort"] == "high"
        assert result["reasoningConfig"]["type"] == "enabled"

    def test_apply_variant_bedrock_unknown_effort(self):
        result = apply_variant("bedrock", "amazon.nova-pro-v1:0", "xhigh", "bedrock")
        # Nova only supports low/medium/high — xhigh not available
        assert result == {}

    def test_list_efforts_nova(self):
        efforts = list_efforts("bedrock", "amazon.nova-pro-v1:0", "bedrock")
        assert sorted(efforts) == ["high", "low", "medium"]

    def test_list_efforts_claude(self):
        efforts = list_efforts("bedrock", "anthropic.claude-3-haiku", "bedrock")
        assert "high" in efforts
        assert "max" in efforts

    def test_non_bedrock_unchanged(self):
        """Verify non-Bedrock providers are unaffected by the new Bedrock case."""
        variants = compute_variants("openai", "gpt-4o", "openai")
        for opts in variants.values():
            # OpenAI should use reasoningEffort, not reasoningConfig
            assert "reasoningConfig" not in opts


class TestBedrockReasoningConfigIntegration:
    """Test that Bedrock reasoningConfig integrates correctly with apply_variant."""

    def test_apply_returns_dict(self):
        result = apply_variant("bedrock_1", "amazon.nova-pro-v1:0", "high", "bedrock")
        assert isinstance(result, dict)

    def test_apply_adaptive_opus_46(self):
        result = apply_variant("bedrock", "anthropic.claude-opus-4-6", "high", "bedrock")
        assert result["reasoningConfig"]["type"] == "adaptive"
        assert result["reasoningConfig"]["maxReasoningEffort"] == "high"

    def test_apply_budget_tokens_claude(self):
        result = apply_variant("bedrock", "anthropic.claude-3-opus", "max", "bedrock")
        assert result["reasoningConfig"]["budgetTokens"] == 31999
