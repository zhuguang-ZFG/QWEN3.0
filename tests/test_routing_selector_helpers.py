"""Tests for routing_selector/helpers.py — predicates and pinning."""

from routing_selector.helpers import (
    _has_valid_key,
    _is_strong_coding_tool_backend,
    _prioritize,
)


class TestHasValidKey:
    def test_no_key_returns_false(self):
        assert _has_valid_key("nonexistent_backend") is False

    def test_empty_key_returns_false(self):
        cfg = {}
        from backends_registry import BACKENDS

        old = BACKENDS.get("test_be_nk", {})
        BACKENDS["test_be_nk"] = {"key": ""}
        try:
            assert _has_valid_key("test_be_nk") is False
        finally:
            if old:
                BACKENDS["test_be_nk"] = old
            else:
                BACKENDS.pop("test_be_nk", None)

    def test_none_key_returns_false(self):
        from backends_registry import BACKENDS

        BACKENDS["test_be_nk2"] = {"key": "none"}
        try:
            assert _has_valid_key("test_be_nk2") is False
        finally:
            BACKENDS.pop("test_be_nk2", None)


class TestIsStrongCodingToolBackend:
    def test_in_list_returns_true(self):
        """Backend with _code suffix is always strong."""
        assert _is_strong_coding_tool_backend("anything_code") is True

    def test_code_suffix_returns_true(self):
        assert _is_strong_coding_tool_backend("test_backend_code") is True

    def test_regular_backend_returns_false(self):
        assert _is_strong_coding_tool_backend("regular_backend") is False

    def test_code_cap_returns_true(self):
        assert _is_strong_coding_tool_backend("cb", {"caps": ["code"]}) is True

    def test_empty_cfg_returns_false(self):
        assert _is_strong_coding_tool_backend("unknown") is False


class TestPrioritize:
    def test_pinned_first(self):
        result = _prioritize("b", ["a", "b", "c"])
        assert result[0] == "b"
        assert "a" in result
        assert "c" in result

    def test_pinned_already_first(self):
        result = _prioritize("a", ["a", "b", "c"])
        assert result == ["a", "b", "c"]

    def test_pinned_not_in_list(self):
        result = _prioritize("x", ["a", "b"])
        assert result == ["x", "a", "b"]

    def test_empty_backends(self):
        result = _prioritize("a", [])
        assert result == ["a"]
