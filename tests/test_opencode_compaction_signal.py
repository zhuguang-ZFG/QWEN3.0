"""Tests for opencode_compaction_signal.py — compaction trigger logic."""

import pytest

from opencode_compaction_signal import (
    COMPACTION_BUFFER,
    PRUNE_MINIMUM,
    PRUNE_PROTECT,
    SIGNAL_COMPACT,
    SIGNAL_CRITICAL,
    SIGNAL_OK,
    SIGNAL_WARNING,
    build_compaction_response_headers,
    compute_usable,
    evaluate_compaction_signal,
    inject_compaction_signal_in_response,
    is_overflow,
    should_trigger_compaction,
)


class TestComputeUsable:
    """compute_usable() tests."""

    def test_with_max_output(self):
        # usable = 128000 - min(20000, 16384) = 128000 - 16384
        assert compute_usable(128_000, 16_384) == 128_000 - 16_384

    def test_without_max_output(self):
        # usable = 128000 - COMPACTION_BUFFER = 128000 - 20000
        assert compute_usable(128_000) == 128_000 - COMPACTION_BUFFER

    def test_small_context(self):
        # usable = 10000 - min(20000, 8192) = 10000 - 8192 = 1808
        assert compute_usable(10_000, 8_192) == 1808

    def test_zero_context(self):
        assert compute_usable(0) == 0

    def test_negative_context(self):
        assert compute_usable(-100) == 0

    def test_large_max_output(self):
        # max_output > COMPACTION_BUFFER → reserved = COMPACTION_BUFFER
        assert compute_usable(128_000, 50_000) == 128_000 - COMPACTION_BUFFER


class TestIsOverflow:
    """is_overflow() tests."""

    def test_at_limit(self):
        assert is_overflow(100_000, 100_000) is True

    def test_over_limit(self):
        assert is_overflow(120_000, 100_000) is True

    def test_under_limit(self):
        assert is_overflow(80_000, 100_000) is False

    def test_zero_usable(self):
        assert is_overflow(100, 0) is False


class TestEvaluateCompactionSignal:
    """evaluate_compaction_signal() tests."""

    def test_ok_signal(self):
        result = evaluate_compaction_signal(30_000, 128_000, 16_384)
        assert result["signal"] == SIGNAL_OK
        assert result["should_compact"] is False

    def test_warning_signal(self):
        # usable = 128000 - 16384 = 111616; 70% = ~78131
        result = evaluate_compaction_signal(80_000, 128_000, 16_384)
        assert result["signal"] == SIGNAL_WARNING
        assert result["should_compact"] is False

    def test_critical_signal(self):
        # usable = 111616; 85% = ~94873
        result = evaluate_compaction_signal(96_000, 128_000, 16_384)
        assert result["signal"] == SIGNAL_CRITICAL
        assert result["should_compact"] is True  # auto_compaction=True

    def test_compact_signal(self):
        # usable = 111616; 95% = ~106035
        result = evaluate_compaction_signal(110_000, 128_000, 16_384)
        assert result["signal"] == SIGNAL_COMPACT
        assert result["should_compact"] is True

    def test_auto_disabled(self):
        result = evaluate_compaction_signal(110_000, 128_000, 16_384, auto_compaction=False)
        assert result["signal"] == SIGNAL_COMPACT
        assert result["should_compact"] is False
        assert result["auto_disabled"] is True

    def test_zero_usable(self):
        result = evaluate_compaction_signal(100, 0)
        assert result["signal"] == SIGNAL_COMPACT
        assert result["should_compact"] is True

    def test_usage_percent_calculation(self):
        result = evaluate_compaction_signal(50_000, 128_000, 20_000)
        # usable = 128000 - 20000 = 108000; pct = 50000/108000 ≈ 46.3%
        assert 45 < result["usage_percent"] < 48

    def test_prune_recommendation_present(self):
        result = evaluate_compaction_signal(110_000, 128_000, 16_384)
        assert result["prune_recommendation"] is not None
        assert result["prune_recommendation"]["protect_tokens"] == PRUNE_PROTECT

    def test_no_prune_when_ok(self):
        result = evaluate_compaction_signal(10_000, 128_000, 16_384)
        assert result["prune_recommendation"] is None


class TestBuildCompactionResponseHeaders:
    """build_compaction_response_headers() tests."""

    def test_ok_headers(self):
        result = evaluate_compaction_signal(10_000, 128_000)
        headers = build_compaction_response_headers(result)
        assert headers["x-lima-compaction-hint"] == "ok"
        assert "x-lima-should-compact" not in headers

    def test_compact_headers(self):
        result = evaluate_compaction_signal(110_000, 128_000, 16_384)
        headers = build_compaction_response_headers(result)
        assert headers["x-lima-compaction-hint"] == "compact"
        assert headers["x-lima-should-compact"] == "true"
        assert "x-lima-prune-tokens" in headers


class TestInjectCompactionSignal:
    """inject_compaction_signal_in_response() tests."""

    def test_ok_no_injection(self):
        body = {"choices": [{"message": {"content": "hi"}}]}
        result = evaluate_compaction_signal(10_000, 128_000)
        injected = inject_compaction_signal_in_response(body, result)
        assert "_lima_compaction" not in injected

    def test_warning_injection(self):
        body = {"choices": [{"message": {"content": "hi"}}]}
        result = evaluate_compaction_signal(80_000, 128_000, 16_384)
        injected = inject_compaction_signal_in_response(body, result)
        assert "_lima_compaction" in injected
        assert injected["_lima_compaction"]["signal"] in ("warning", "critical", "compact")


class TestShouldTriggerCompaction:
    """should_trigger_compaction() tests."""

    def test_low_usage(self):
        messages = [{"role": "user", "content": "hi"}]
        assert should_trigger_compaction(messages, "google_flash") is False

    def test_high_usage(self):
        # Create messages that would estimate high token usage
        big_text = "x " * 50000  # ~25000 tokens estimate
        messages = [{"role": "user", "content": big_text}]
        # Use a small context window backend
        assert should_trigger_compaction(messages, "scnet_qwen30b") is True
