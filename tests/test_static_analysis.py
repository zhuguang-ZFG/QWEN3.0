"""Tests for context_pipeline.lab.static_analysis typed symbol extraction."""

from context_pipeline.lab.static_analysis import (
    extract_typed_symbols,
    is_module_eligible,
)


def test_extract_typed_symbols_from_function_with_annotations():
    source = """
def add(a: int, b: int) -> int:
    \"\"\"Add two integers.\"\"\"
    return a + b
"""
    symbols = extract_typed_symbols(source)
    assert len(symbols) == 1
    assert symbols[0].name == "add"
    assert symbols[0].kind == "function"
    assert symbols[0].type_hints == {"a": "int", "b": "int", "returns": "int"}
    assert "Add two integers" in symbols[0].docstring


def test_extract_typed_symbols_from_async_function():
    source = """
async def fetch(url: str) -> dict:
    return {}
"""
    symbols = extract_typed_symbols(source)
    assert len(symbols) == 1
    assert symbols[0].kind == "async_function"
    assert symbols[0].type_hints["returns"] == "dict"


def test_extract_typed_symbols_from_class():
    source = """
class Router:
    \"\"\"A routing engine.\"\"\"
    pass
"""
    symbols = extract_typed_symbols(source)
    assert len(symbols) == 1
    assert symbols[0].name == "Router"
    assert symbols[0].kind == "class"
    assert "routing engine" in symbols[0].docstring


def test_extract_typed_symbols_from_class_with_bases():
    source = """
class MyIndex(VectorIndex, Protocol):
    pass
"""
    symbols = extract_typed_symbols(source)
    assert len(symbols) == 1
    hints = symbols[0].type_hints
    assert "bases" in hints
    assert "VectorIndex" in hints["bases"]


def test_extract_typed_symbols_from_annotated_variable():
    source = """
store: int = 0
"""
    symbols = extract_typed_symbols(source)
    assert any(s.name == "store" and s.kind == "variable" for s in symbols)


def test_extract_typed_symbols_handles_syntax_error():
    assert extract_typed_symbols("def broken(:") == []


def test_module_eligible_default_off(monkeypatch):
    monkeypatch.delenv("LIMA_STATIC_ANALYSIS", raising=False)
    assert not is_module_eligible("routing_engine.py")


def test_module_eligible_in_allowlist(monkeypatch):
    monkeypatch.setenv("LIMA_STATIC_ANALYSIS", "1")
    assert is_module_eligible("routing_engine.py")
    assert is_module_eligible("backends.py")
    assert not is_module_eligible("obscure_script.py")
