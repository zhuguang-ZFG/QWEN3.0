"""Tests for M2: multi-language code context, SQLite graph, ChromaDB vector store."""

from __future__ import annotations

import os


from code_context.ast_adapter import (
    FileAst,
    StdlibAstExtractor,
    get_extractor,
)
from code_context.graph_index import (
    InMemoryGraphIndex,
    build_graph_index,
)
from code_context.index_store import InMemoryCodeIndex, CodeSymbol, build_code_index
from code_context.scanner import scan_file, scan_python_file
from code_context.file_watcher import FileWatcher


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


# ---------------------------------------------------------------------------
# Scanner - multi-language dispatch
# ---------------------------------------------------------------------------


class TestScanner:
    def test_scan_python_file(self, tmp_path):
        p = tmp_path / "test.py"
        p.write_text("class Foo:\n    def bar(self): pass")
        record = scan_file(p)
        assert len(record.symbols) >= 1
        assert record.path == str(p)

    def test_scan_typescript_file(self, tmp_path):
        p = tmp_path / "app.ts"
        p.write_text("export function run(): void {}\nexport class App {}")
        record = scan_file(p)
        names = {s.name for s in record.symbols}
        assert "run" in names
        assert "App" in names

    def test_scan_unknown_extension(self, tmp_path):
        p = tmp_path / "data.xyz"
        p.write_text("hello")
        record = scan_file(p)
        assert len(record.symbols) == 0

    def test_legacy_scan_python_file(self, tmp_path):
        p = tmp_path / "old.py"
        p.write_text("def legacy(): pass")
        record = scan_python_file(p)
        assert any(s.name == "legacy" for s in record.symbols)


# ---------------------------------------------------------------------------
# InMemoryGraphIndex
# ---------------------------------------------------------------------------


class TestInMemoryGraphIndex:
    def test_add_and_search(self):
        g = InMemoryGraphIndex()
        g.add_relation("server.py", "routing_engine.py", "imports")
        g.add_relation("routing_engine.py", "http_caller.py", "calls")
        results = g.search(["server.py"], max_depth=2)
        entities = {r.entity for r in results}
        assert "routing_engine.py" in entities
        assert "http_caller.py" in entities

    def test_edge_count(self):
        g = InMemoryGraphIndex()
        assert g.edge_count == 0
        g.add_relation("a.py", "b.py", "imports")
        assert g.edge_count == 1


# ---------------------------------------------------------------------------
# SQLite Graph Index
# ---------------------------------------------------------------------------


class TestSqliteGraphIndex:
    def test_persistence(self, tmp_path):
        from code_context.sqlite_graph_store import SqliteGraphIndex

        db = str(tmp_path / "test_graph.db")
        g1 = SqliteGraphIndex(db)
        g1.add_relation("a.py", "b.py", "imports")
        g1.add_relation("b.py", "c.py", "calls")
        assert g1.edge_count >= 2
        g1.close()

        g2 = SqliteGraphIndex(db)
        assert g2.edge_count >= 2
        results = g2.search(["a.py"], max_depth=2)
        entities = {r.entity for r in results}
        assert "b.py" in entities
        g2.close()

    def test_fts_search(self, tmp_path):
        from code_context.sqlite_graph_store import SqliteGraphIndex

        db = str(tmp_path / "fts_test.db")
        g = SqliteGraphIndex(db)
        g.add_relation("server.py", "routing.py", "imports")
        results = g.fts_search("server")
        assert len(results) >= 1
        g.close()

    def test_clear(self, tmp_path):
        from code_context.sqlite_graph_store import SqliteGraphIndex

        db = str(tmp_path / "clear_test.db")
        g = SqliteGraphIndex(db)
        g.add_relation("a.py", "b.py", "imports")
        assert g.edge_count >= 1
        g.clear()
        assert g.edge_count == 0
        g.close()


# ---------------------------------------------------------------------------
# InMemoryCodeIndex
# ---------------------------------------------------------------------------


class TestInMemoryCodeIndex:
    def test_upsert_and_search(self):
        idx = InMemoryCodeIndex()
        idx.upsert_file(
            "server.py",
            [CodeSymbol("main", "function", 1)],
            [("fastapi", 1)],
            mtime=1.0,
        )
        results = idx.search("server fastapi")
        assert len(results) >= 1
        assert results[0].path == "server.py"

    def test_keyword_search(self):
        idx = InMemoryCodeIndex()
        idx.upsert_file("a.py", [CodeSymbol("foo", "function", 1)], [], mtime=1.0)
        idx.upsert_file("b.py", [CodeSymbol("bar", "function", 1)], [], mtime=1.0)
        results = idx.search("foo")
        assert any(r.path == "a.py" for r in results)


# ---------------------------------------------------------------------------
# FileWatcher
# ---------------------------------------------------------------------------


class TestFileWatcher:
    def test_detect_new_files(self, tmp_path):
        (tmp_path / "a.py").write_text("def a(): pass")
        watcher = FileWatcher(root_path=str(tmp_path))
        paths, changes = watcher.scan()
        assert len(paths) == 1
        assert changes[0].change_type == "created"

    def test_detect_modified_files(self, tmp_path):
        import time

        (tmp_path / "a.py").write_text("def a(): pass")
        watcher = FileWatcher(root_path=str(tmp_path))
        watcher.scan()

        time.sleep(0.05)
        (tmp_path / "a.py").write_text("def a():\n    pass")
        paths, changes = watcher.scan()
        assert len(paths) == 1
        assert changes[0].change_type == "modified"

    def test_detect_deleted_files(self, tmp_path):
        (tmp_path / "a.py").write_text("def a(): pass")
        watcher = FileWatcher(root_path=str(tmp_path))
        watcher.scan()

        (tmp_path / "a.py").unlink()
        paths, changes = watcher.scan()
        assert any(c.change_type == "deleted" for c in changes)

    def test_ignores_non_python_files(self, tmp_path):
        (tmp_path / "readme.md").write_text("# Hello")
        (tmp_path / "data.json").write_text("{}")
        watcher = FileWatcher(root_path=str(tmp_path))
        paths, _ = watcher.scan()
        assert len(paths) == 0

    def test_includes_typescript(self, tmp_path):
        (tmp_path / "app.ts").write_text("export const x = 1;")
        watcher = FileWatcher(root_path=str(tmp_path))
        paths, _ = watcher.scan()
        assert len(paths) == 1

    def test_no_changes_on_rescan(self, tmp_path):
        (tmp_path / "a.py").write_text("def a(): pass")
        watcher = FileWatcher(root_path=str(tmp_path))
        watcher.scan()
        paths, changes = watcher.scan()
        assert len(paths) == 0
        assert len(changes) == 0


# ---------------------------------------------------------------------------
# Factory functions
# ---------------------------------------------------------------------------


class TestFactories:
    def test_build_graph_index_default(self):
        os.environ.pop("LIMA_DATA_DIR", None)
        g = build_graph_index()
        assert isinstance(g, InMemoryGraphIndex)

    def test_build_graph_index_persistent(self, tmp_path):
        fresh = tmp_path / "fresh_graph"
        fresh.mkdir()
        os.environ["LIMA_DATA_DIR"] = str(fresh)
        try:
            g = build_graph_index()
            g.add_relation("a.py", "b.py", "imports")
            assert g.edge_count >= 1
        finally:
            os.environ.pop("LIMA_DATA_DIR", None)

    def test_build_code_index_default(self):
        os.environ.pop("LIMA_DATA_DIR", None)
        idx = build_code_index()
        assert isinstance(idx, InMemoryCodeIndex)
