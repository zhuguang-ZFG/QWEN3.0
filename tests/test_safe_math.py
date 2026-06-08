"""Tests for bounded math evaluation helper."""

import pytest

from lima_fc_tools.safe_math import evaluate_math_expression


def test_evaluate_basic_arithmetic():
    assert evaluate_math_expression("1 + 2 * 3") == 7.0


def test_evaluate_allows_math_functions():
    assert evaluate_math_expression("sqrt(9) + sin(0)") == 3.0


def test_evaluate_rejects_huge_exponent():
    with pytest.raises(ValueError):
        evaluate_math_expression("2 ** 9999")


def test_evaluate_rejects_code_injection():
    with pytest.raises(ValueError):
        evaluate_math_expression("__import__('os').system('echo hi')")
