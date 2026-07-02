"""Tests for observability/cli_telemetry.py — sanitized CLI telemetry."""

from observability.cli_telemetry import _short, _int, _error_class


class TestShort:
    def test_empty_value(self):
        assert _short(None) == ""

    def test_truncates_long_value(self):
        long_value = "x" * 100
        assert len(_short(long_value)) == 80

    def test_short_value_unchanged(self):
        assert _short("hello") == "hello"


class TestInt:
    def test_none_default(self):
        assert _int(None) == 0

    def test_int_value(self):
        assert _int("42") == 42

    def test_float_string(self):
        assert _int("3.14") == 3


class TestErrorClass:
    def test_timeout(self):
        assert _error_class("ReadTimeout") == "timeout"

    def test_connection(self):
        assert _error_class("Connection refused") == "network_or_provider"

    def test_unknown(self):
        assert _error_class("Something weird") == "provider_error"
