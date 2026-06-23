"""Tests for code_context/retriever.py — retrieval facade."""

from unittest.mock import MagicMock

from code_context.retriever import retrieve_relevant_files


class TestRetrieveRelevantFiles:
    def test_keyword_search(self):
        index = MagicMock()
        index.search.return_value = ["file1.py"]
        result = retrieve_relevant_files(index, "server", limit=3)
        index.search.assert_called_once_with("server", limit=3)
        assert result == ["file1.py"]

    def test_semantic_search(self):
        index = MagicMock()
        index.semantic_search.return_value = ["file2.py"]
        embedding = [0.1, 0.2]
        result = retrieve_relevant_files(index, "server", query_embedding=embedding)
        index.semantic_search.assert_called_once_with(embedding, limit=5)
        assert result == ["file2.py"]
