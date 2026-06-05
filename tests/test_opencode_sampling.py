"""Tests for opencode_sampling.py — model-level sampling parameter resolution."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from opencode_sampling import resolve_temperature, resolve_top_p, resolve_top_k, resolve_sampling_params


class TestResolveTemperature:
    def test_qwen(self):
        assert resolve_temperature("qwen-plus") == 0.55
        assert resolve_temperature("Qwen3-235B") == 0.55

    def test_gemini(self):
        assert resolve_temperature("gemini-2.5-pro") == 1.0
        assert resolve_temperature("gemini-1.5-flash") == 1.0

    def test_glm(self):
        assert resolve_temperature("glm-4.6") == 1.0
        assert resolve_temperature("glm-4.7") == 1.0

    def test_minimax(self):
        assert resolve_temperature("MiniMax-M2") == 1.0

    def test_kimi_thinking(self):
        assert resolve_temperature("kimi-k2-thinking") == 1.0

    def test_kimi_non_thinking(self):
        t = resolve_temperature("kimi-k2")
        assert t == 0.6

    def test_unknown_model(self):
        assert resolve_temperature("gpt-4o") is None

    def test_claude(self):
        assert resolve_temperature("claude-3.5-sonnet") is None


class TestResolveTopP:
    def test_qwen(self):
        assert resolve_top_p("qwen-max") == 1.0

    def test_minimax(self):
        assert resolve_top_p("MiniMax-M2") == 0.95

    def test_gemini(self):
        assert resolve_top_p("gemini-2.5-pro") == 0.95

    def test_kimi_k25(self):
        assert resolve_top_p("kimi-k2.5") == 0.95

    def test_unknown(self):
        assert resolve_top_p("gpt-4o") is None


class TestResolveTopK:
    def test_gemini(self):
        assert resolve_top_k("gemini-2.5-pro") == 64

    def test_minimax_m2(self):
        tk = resolve_top_k("MiniMax-M2")
        assert tk is not None and 20 <= tk <= 40

    def test_unknown(self):
        assert resolve_top_k("gpt-4o") is None


class TestResolveSamplingParams:
    def test_qwen_returns_temp_and_topp(self):
        params = resolve_sampling_params("qwen-plus", "qwen")
        assert "temperature" in params
        assert params["temperature"] == 0.55
        assert "top_p" in params

    def test_gemini_returns_all_three(self):
        params = resolve_sampling_params("gemini-2.5-pro", "google_gemini")
        assert params["temperature"] == 1.0
        assert params["top_p"] == 0.95
        assert params["top_k"] == 64

    def test_gpt4o_empty(self):
        params = resolve_sampling_params("gpt-4o", "openai")
        assert params == {}

    def test_no_overwrite_existing(self):
        """Sampling params should not overwrite if key already exists in body."""
        # This is tested via integration in http_request_builder
        params = resolve_sampling_params("qwen-plus", "qwen")
        body = {"temperature": 0.9}  # pre-set
        for k, v in params.items():
            if k not in body:
                body[k] = v
        assert body["temperature"] == 0.9  # not overwritten
