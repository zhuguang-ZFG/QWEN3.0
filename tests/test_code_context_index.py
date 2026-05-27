from pathlib import Path

from code_context.scanner import scan_python_file
from code_context.index_store import CodeSymbol, InMemoryCodeIndex, _cosine_similarity
from code_context.retriever import retrieve_relevant_files


def test_scan_python_file_extracts_classes_functions_and_imports(tmp_path: Path):
    target = tmp_path / "sample.py"
    target.write_text(
        "import os\n"
        "from pathlib import Path\n\n"
        "class Worker:\n"
        "    def run(self):\n"
        "        return Path(os.getcwd())\n\n"
        "def helper():\n"
        "    return 'ok'\n",
        encoding="utf-8",
    )

    record = scan_python_file(target)

    assert record.path == str(target)
    assert ("os", 1) in record.imports
    assert ("pathlib.Path", 2) in record.imports
    assert CodeSymbol(name="Worker", kind="class", line=4) in record.symbols
    assert CodeSymbol(name="run", kind="function", line=5) in record.symbols
    assert CodeSymbol(name="helper", kind="function", line=8) in record.symbols


def test_in_memory_index_finds_symbols_by_query():
    index = InMemoryCodeIndex()
    index.upsert_file(
        path="routing_engine.py",
        symbols=[CodeSymbol(name="select", kind="function", line=120)],
        imports=[],
        mtime=1.0,
    )

    matches = index.search("select backend")

    assert matches[0].path == "routing_engine.py"
    assert matches[0].symbols[0].name == "select"


def test_cosine_similarity_identical_vectors():
    a = [1.0, 0.0, 0.0]
    b = [1.0, 0.0, 0.0]
    assert abs(_cosine_similarity(a, b) - 1.0) < 1e-6


def test_cosine_similarity_orthogonal_vectors():
    a = [1.0, 0.0, 0.0]
    b = [0.0, 1.0, 0.0]
    assert abs(_cosine_similarity(a, b)) < 1e-6


def test_semantic_search_ranks_by_cosine_similarity():
    index = InMemoryCodeIndex()
    index.upsert_file(
        path="routing_engine.py",
        symbols=[CodeSymbol(name="select", kind="function", line=10)],
        imports=[],
        mtime=1.0,
        embedding=[0.9, 0.1, 0.0],
    )
    index.upsert_file(
        path="health_tracker.py",
        symbols=[CodeSymbol(name="check", kind="function", line=5)],
        imports=[],
        mtime=1.0,
        embedding=[0.1, 0.9, 0.0],
    )

    query_emb = [0.85, 0.15, 0.0]
    matches = index.semantic_search(query_emb, limit=2)

    assert matches[0].path == "routing_engine.py"
    assert matches[1].path == "health_tracker.py"


def test_semantic_search_skips_files_without_embeddings():
    index = InMemoryCodeIndex()
    index.upsert_file(
        path="with_emb.py",
        symbols=[],
        imports=[],
        mtime=1.0,
        embedding=[0.5, 0.5, 0.0],
    )
    index.upsert_file(
        path="no_emb.py",
        symbols=[],
        imports=[],
        mtime=1.0,
    )

    matches = index.semantic_search([0.5, 0.5, 0.0], limit=5)

    assert len(matches) == 1
    assert matches[0].path == "with_emb.py"


def test_retriever_facade_preserves_planned_import_boundary():
    index = InMemoryCodeIndex()
    index.upsert_file(
        path="routing_engine.py",
        symbols=[CodeSymbol(name="select_backend", kind="function", line=10)],
        imports=[],
        mtime=1.0,
    )

    matches = retrieve_relevant_files(index, "select backend")

    assert matches[0].path == "routing_engine.py"


# -- graph_index -----------------------------------------------------------------

def test_in_memory_graph_index_add_and_get_related():
    from code_context.graph_index import InMemoryGraphIndex

    g = InMemoryGraphIndex()
    g.add_relation("a.py", "b.py", "imports")
    g.add_relation("a.py", "Calculator", "defines_class")

    related = g.get_related("a.py", max_depth=1)
    assert len(related) >= 2
    targets = {r.target for r in related}
    assert "b.py" in targets
    assert "Calculator" in targets


def test_in_memory_graph_index_bfs_depth_limit():
    from code_context.graph_index import InMemoryGraphIndex

    g = InMemoryGraphIndex()
    g.add_relation("a.py", "b.py", "imports")
    g.add_relation("b.py", "c.py", "imports")
    g.add_relation("c.py", "d.py", "imports")

    # depth=2: processes a.py, b.py, c.py - all their outgoing edges
    depth2 = {r.target for r in g.get_related("a.py", max_depth=2)}
    assert "d.py" in depth2

    # depth=0: only processes a.py - only a.py's immediate neighbors
    depth0 = {r.target for r in g.get_related("a.py", max_depth=0)}
    assert "b.py" in depth0
    assert "c.py" not in depth0
    assert "d.py" not in depth0


def test_in_memory_graph_index_search():
    from code_context.graph_index import InMemoryGraphIndex

    g = InMemoryGraphIndex()
    g.add_relation("mod_a.py", "mod_b.py", "imports")
    g.add_relation("mod_a.py", "Helper", "defines_class")
    g.add_relation("mod_b.py", "Util", "defines_class")

    results = g.search(["mod_a.py"], max_depth=2, max_results=10)
    assert len(results) >= 2


def test_in_memory_graph_index_edge_count():
    from code_context.graph_index import InMemoryGraphIndex

    g = InMemoryGraphIndex()
    assert g.edge_count == 0
    g.add_relation("a.py", "b.py", "imports")
    assert g.edge_count == 1


def test_graph_index_is_abstract():
    from code_context.graph_index import GraphIndex
    import pytest

    with pytest.raises(TypeError):
        GraphIndex()


def test_build_graph_index_factory():
    from code_context.graph_index import build_graph_index, InMemoryGraphIndex

    g = build_graph_index()
    assert isinstance(g, InMemoryGraphIndex)


# -- ast_adapter -----------------------------------------------------------------

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
