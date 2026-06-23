"""Tests for code_context index core (scanner, index_store, retriever)."""

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
