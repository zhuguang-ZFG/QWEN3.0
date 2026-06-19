"""Tests for the AST adapter (stdlib Python and tree-sitter fallback)."""

from code_context.ast_adapter import (
    FileAst,
    StdlibAstExtractor,
    get_extractor,
)


# ---------------------------------------------------------------------------
# AST Adapter - existing Python extractor
# ---------------------------------------------------------------------------


class TestStdlibAstExtractor:
    def test_extract_python_symbols(self, tmp_path):
        p = tmp_path / "test.py"
        p.write_text("class Foo:\n    def bar(self): pass\ndef baz(): pass")
        ext = StdlibAstExtractor()
        symbols = ext.extract_symbols(p)
        names = {s.name for s in symbols}
        assert "Foo" in names
        assert "bar" in names
        assert "baz" in names

    def test_extract_python_relations(self, tmp_path):
        p = tmp_path / "test.py"
        p.write_text("import os\nfrom pathlib import Path")
        ext = StdlibAstExtractor()
        module_map = {"os": "os", "pathlib": "pathlib", "Path": "pathlib"}
        rels = ext.extract_relations(p, module_map=module_map)
        targets = {r.target for r in rels}
        assert "os" in targets

    def test_scan_file(self, tmp_path):
        p = tmp_path / "test.py"
        p.write_text("class MyClass:\n    pass")
        ext = StdlibAstExtractor()
        ast = ext.scan_file(p)
        assert isinstance(ast, FileAst)
        assert ast.language == "python"
        assert any(s.name == "MyClass" for s in ast.symbols)

    def test_factory_returns_python(self):
        ext = get_extractor("python")
        assert isinstance(ext, StdlibAstExtractor)

    def test_factory_returns_none_for_unknown(self):
        ext = get_extractor("brainfuck")
        assert ext is None


# ---------------------------------------------------------------------------
# Tree-sitter adapter (regex fallback mode)
# ---------------------------------------------------------------------------


class TestTreeSitterAdapter:
    def test_typescript_symbols(self, tmp_path):
        p = tmp_path / "test.ts"
        p.write_text("export function hello(): void {}\nexport class Foo {}")
        ext = get_extractor("typescript")
        assert ext is not None
        symbols = ext.extract_symbols(p)
        names = {s.name for s in symbols}
        assert "hello" in names
        assert "Foo" in names

    def test_javascript_symbols(self, tmp_path):
        p = tmp_path / "test.js"
        p.write_text("function main() {}\nconst App = () => {};")
        ext = get_extractor("javascript")
        assert ext is not None
        symbols = ext.extract_symbols(p)
        names = {s.name for s in symbols}
        assert "main" in names

    def test_go_symbols(self, tmp_path):
        p = tmp_path / "main.go"
        p.write_text("package main\nfunc main() {}\ntype Server struct{}")
        ext = get_extractor("go")
        assert ext is not None
        symbols = ext.extract_symbols(p)
        names = {s.name for s in symbols}
        assert "main" in names
        assert "Server" in names

    def test_rust_symbols(self, tmp_path):
        p = tmp_path / "lib.rs"
        p.write_text("pub fn hello() {}\npub struct Config {}")
        ext = get_extractor("rust")
        assert ext is not None
        symbols = ext.extract_symbols(p)
        names = {s.name for s in symbols}
        assert "hello" in names
        assert "Config" in names

    def test_python_import_relations(self, tmp_path):
        p = tmp_path / "test.py"
        p.write_text("import os\nfrom pathlib import Path")
        ext = get_extractor("python")
        assert ext is not None
        module_map = {"os": "os", "pathlib": "pathlib"}
        rels = ext.extract_relations(p, module_map=module_map)
        assert any("os" in r.target for r in rels)

    def test_supported_languages_includes_python(self):
        ext = get_extractor("python")
        assert "python" in ext.supported_languages
