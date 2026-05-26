"""Tests for bounded math evaluation in Telegram FC tools."""

from lima_fc_tools.safe_math import evaluate_math_expression


def test_evaluate_basic_arithmetic():
    assert evaluate_math_expression("1 + 2 * 3") == 7.0


def test_evaluate_allows_math_functions():
    assert evaluate_math_expression("sqrt(9) + sin(0)") == 3.0


def test_evaluate_rejects_huge_exponent():
    try:
        evaluate_math_expression("2 ** 9999")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_evaluate_rejects_code_injection():
    try:
        evaluate_math_expression("__import__('os').system('echo hi')")
        assert False, "expected ValueError"
    except ValueError:
        pass
