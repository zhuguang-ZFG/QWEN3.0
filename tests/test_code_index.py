"""Tests for the in-memory code index."""

from code_context.index_store import InMemoryCodeIndex, CodeSymbol


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
