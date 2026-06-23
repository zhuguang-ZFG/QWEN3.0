"""Tests for common/type_helpers.py — type coercion helpers."""

from common.type_helpers import _safe_int, _number


class TestSafeInt:
    def test_int_value(self):
        assert _safe_int(42) == 42

    def test_string_int(self):
        assert _safe_int("42") == 42

    def test_invalid_returns_zero(self):
        assert _safe_int("abc") == 0

    def test_none_returns_zero(self):
        assert _safe_int(None) == 0


class TestNumber:
    def test_int(self):
        assert _number(42) == 42.0

    def test_float(self):
        assert _number(3.14) == 3.14

    def test_string_number(self):
        assert _number("3.14") == 3.14

    def test_bool_returns_default(self):
        assert _number(True) == 0.0

    def test_invalid_returns_default(self):
        assert _number("abc", default=1.0) == 1.0
