"""Tests for session_memory/eval_gate_promotion.py — promotion application."""

from unittest.mock import patch

from session_memory.eval_gate_promotion import apply_promotion


class TestApplyPromotion:
    def test_empty_pattern_key(self):
        result = apply_promotion("")
        assert result["applied"] is False

    def test_pattern_key_too_long(self):
        result = apply_promotion("x" * 161)
        assert result["applied"] is False

    def test_not_found(self):
        with patch(
            "session_memory.eval_gate_promotion._find_approved_candidate",
            return_value=None,
        ):
            result = apply_promotion("missing")
            assert result["applied"] is False
            assert "not found" in result["error"]
