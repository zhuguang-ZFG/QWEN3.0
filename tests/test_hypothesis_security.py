"""Hypothesis property tests for security-critical public API tools."""

from __future__ import annotations

import pytest
from hypothesis import given, settings, strategies as st

from channel_gateway.public_apis import fetch_calc


@given(
    expr=st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs",),  # no surrogates
            blacklist_characters="\x00",
        ),
        min_size=1,
        max_size=60,
    )
)
@settings(max_examples=200)
def test_fetch_calc_never_crashes(expr: str):
    """The AST-sandboxed calculator should handle any input without crashing."""
    result = fetch_calc(expr)
    assert isinstance(result, dict)
    assert "ok" in result
    # If it succeeded, the result must be numeric or error
    if result["ok"]:
        assert "text" in result
    else:
        assert "error" in result


@pytest.mark.parametrize("expr,expected_text", [
    ("2 + 2", "2 + 2 = 4"),
    ("3 * 4", "3 * 4 = 12"),
    ("(1 + 2) * 3", "(1 + 2) * 3 = 9"),
    ("-5 + 3", "-5 + 3 = -2"),
    ("3.14 * 2", "3.14 * 2 = 6.28"),
])
def test_fetch_calc_correct_results(expr, expected_text):
    result = fetch_calc(expr)
    assert result["ok"] is True
    assert result["text"] == expected_text


@given(st.integers(min_value=-1000, max_value=1000))
@settings(max_examples=100)
def test_fetch_calc_identity(n: int):
    """n + 0 should equal n, n * 1 should equal n."""
    r1 = fetch_calc(f"{n} + 0")
    assert r1["ok"]
    assert f"{n + 0:g}" in r1["text"]

    r2 = fetch_calc(f"{n} * 1")
    assert r2["ok"]
    assert f"{n * 1:g}" in r2["text"]


def test_fetch_calc_rejects_invalid_syntax():
    """Letters, imports, and function calls should be rejected by the regex guard."""
    assert not fetch_calc("__import__('os')")["ok"]
    assert not fetch_calc("exec('1')")["ok"]
    assert not fetch_calc("open('/')")["ok"]
    assert not fetch_calc("1; import os")["ok"]


def test_fetch_calc_rejects_attribute_access():
    """Attribute access like 'os'.system should be rejected."""
    r = fetch_calc("''.__class__")
    assert not r["ok"]
