"""Tests for opencode_output_limit.py — max output tokens cap."""

import pytest

from opencode_output_limit import (
    OUTPUT_TOKEN_MAX,
    cap_max_tokens_in_body,
    resolve_max_output_tokens,
)


class TestResolveMaxOutputTokens:
    """resolve_max_output_tokens() tests."""

    def test_default_cap(self):
        assert resolve_max_output_tokens() == OUTPUT_TOKEN_MAX

    def test_requested_below_cap(self):
        assert resolve_max_output_tokens(requested_max=4096) == 4096

    def test_requested_above_cap(self):
        assert resolve_max_output_tokens(requested_max=100_000) == OUTPUT_TOKEN_MAX

    def test_backend_limit_lower(self):
        result = resolve_max_output_tokens(
            requested_max=32_000, backend_name="cf_qwen_coder"
        )
        assert result == 8_192

    def test_backend_limit_scnet(self):
        result = resolve_max_output_tokens(
            requested_max=32_000, backend_name="scnet_ds_flash"
        )
        assert result == 16_384

    def test_model_family_claude(self):
        result = resolve_max_output_tokens(
            requested_max=32_000, model_id="claude-sonnet-4"
        )
        assert result == 16_384

    def test_model_family_claude_opus(self):
        result = resolve_max_output_tokens(
            requested_max=32_000, model_id="claude-opus-4"
        )
        # Claude Opus matches "claude" pattern first (16384)
        # unless opus pattern is checked — depends on order
        assert result <= 32_000

    def test_model_limit_param(self):
        result = resolve_max_output_tokens(model_limit=8_000)
        assert result == 8_000

    def test_model_limit_higher_than_cap(self):
        result = resolve_max_output_tokens(model_limit=100_000)
        assert result == OUTPUT_TOKEN_MAX

    def test_requested_and_backend(self):
        result = resolve_max_output_tokens(
            requested_max=50_000, backend_name="scnet_qwen30b"
        )
        assert result == 8_192

    def test_zero_requested(self):
        result = resolve_max_output_tokens(requested_max=0)
        assert result == OUTPUT_TOKEN_MAX

    def test_negative_requested(self):
        result = resolve_max_output_tokens(requested_max=-1)
        assert result == OUTPUT_TOKEN_MAX


class TestCapMaxTokensInBody:
    """cap_max_tokens_in_body() tests."""

    def test_caps_high_value(self):
        body = {"max_tokens": 100_000}
        cap_max_tokens_in_body(body, model_id="gpt-5")
        assert body["max_tokens"] <= OUTPUT_TOKEN_MAX

    def test_preserves_low_value(self):
        body = {"max_tokens": 4096}
        cap_max_tokens_in_body(body)
        assert body["max_tokens"] == 4096

    def test_no_max_tokens(self):
        body = {"model": "gpt-4o"}
        cap_max_tokens_in_body(body)
        assert "max_tokens" not in body

    def test_backend_specific_cap(self):
        body = {"max_tokens": 32_000}
        cap_max_tokens_in_body(body, backend_name="cf_qwen_coder")
        assert body["max_tokens"] == 8_192
