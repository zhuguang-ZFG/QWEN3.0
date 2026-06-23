"""Tests for code_context ast_adapter."""

from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "sample_repo"


def test_stdlib_extractor_extracts_symbols():
    from code_context.ast_adapter import StdlibAstExtractor

    ext = StdlibAstExtractor()
    symbols = ext.extract_symbols(FIXTURES_DIR / "module_a.py")

    names = {s.name for s in symbols}
    assert "Calculator" in names
    assert "add" in names
    assert "calculate_sum" in names

    calc = next(s for s in symbols if s.name == "Calculator")
    assert calc.kind == "class"


def test_stdlib_extractor_method_vs_function():
    from code_context.ast_adapter import StdlibAstExtractor

    ext = StdlibAstExtractor()
    symbols = ext.extract_symbols(FIXTURES_DIR / "module_a.py")

    add_symbol = next(s for s in symbols if s.name == "add")
    assert add_symbol.kind == "method"

    calc_sum = next(s for s in symbols if s.name == "calculate_sum")
    assert calc_sum.kind == "function"


def test_stdlib_extractor_relations():
    from code_context.ast_adapter import StdlibAstExtractor

    ext = StdlibAstExtractor()
    relations = ext.extract_relations(
        FIXTURES_DIR / "module_a.py",
        module_map={"module_b": "module_b.py", "sample_repo": "module_b.py"},
    )

    types = {r.relation_type for r in relations}
    assert "imports" in types
    assert "defines_class" in types


def test_stdlib_extractor_resolves_import_from_leaf_module():
    from code_context.ast_adapter import StdlibAstExtractor

    ext = StdlibAstExtractor()
    relations = ext.extract_relations(
        FIXTURES_DIR / "module_a.py",
        module_map={"module_b": "module_b.py"},
    )

    imports = [r for r in relations if r.relation_type == "imports"]
    assert imports
    assert imports[0].target == "module_b.py"


def test_stdlib_extractor_scan_file():
    from code_context.ast_adapter import StdlibAstExtractor

    ext = StdlibAstExtractor()
    file_ast = ext.scan_file(FIXTURES_DIR / "module_a.py")

    assert file_ast.language == "python"
    assert "module_a.py" in file_ast.path
    assert len(file_ast.symbols) >= 5


def test_stdlib_extractor_handles_missing_file():
    from code_context.ast_adapter import StdlibAstExtractor

    ext = StdlibAstExtractor()
    assert ext.extract_symbols(Path("/nonexistent/file.py")) == []
    assert ext.extract_relations(Path("/nonexistent/file.py")) == []


def test_get_extractor_python():
    from code_context.ast_adapter import get_extractor, StdlibAstExtractor

    ext = get_extractor("python")
    assert isinstance(ext, StdlibAstExtractor)


def test_get_extractor_unknown_language():
    from code_context.ast_adapter import get_extractor

    assert get_extractor("brainfuck") is None
    assert get_extractor("cobol") is None


def test_ast_extractor_supported_languages():
    from code_context.ast_adapter import StdlibAstExtractor

    ext = StdlibAstExtractor()
    assert "python" in ext.supported_languages
