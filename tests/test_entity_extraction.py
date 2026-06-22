"""Tests for context_pipeline/entity_extraction.py — code entity extraction."""

from context_pipeline.entity_extraction import extract_entities, ExtractedEntities


class TestExtractedEntities:
    def test_default_values(self):
        e = ExtractedEntities()
        assert e.total_entities == 0
        assert e.to_query_terms() == []

    def test_to_query_terms_includes_paths(self):
        e = ExtractedEntities(file_paths=["main.py"])
        assert "main.py" in e.to_query_terms()

    def test_to_query_terms_limited_to_10(self):
        e = ExtractedEntities(file_paths=[f"f{i}.py" for i in range(20)])
        assert len(e.to_query_terms()) <= 10


class TestExtractEntities:
    def test_empty_messages(self):
        entities = extract_entities([])
        assert entities.total_entities == 0

    def test_empty_user_text(self):
        entities = extract_entities([{"role": "system", "content": "system"}])
        assert entities.total_entities == 0

    def test_extract_file_path(self):
        entities = extract_entities([{"role": "user", "content": "fix server.py"}])
        assert "server.py" in entities.file_paths

    def test_extract_function_name(self):
        entities = extract_entities([{"role": "user", "content": "def route()"}])
        assert "route" in entities.functions

    def test_extract_class_name(self):
        entities = extract_entities([{"role": "user", "content": "class Pipeline"}])
        assert "Pipeline" in entities.classes

    def test_extract_module_name(self):
        entities = extract_entities([{"role": "user", "content": "import os"}])
        assert "os" in entities.modules

    def test_extract_technology(self):
        entities = extract_entities([{"role": "user", "content": "I use FastAPI and Redis"}])
        assert "fastapi" in entities.technologies
        assert "redis" in entities.technologies

    def test_extract_error(self):
        entities = extract_entities([{"role": "user", "content": "got TypeError"}])
        assert "TypeError" in entities.errors

    def test_multiple_messages(self):
        entities = extract_entities([
            {"role": "user", "content": "look at main.py"},
            {"role": "assistant", "content": "ok"},
            {"role": "user", "content": "def start(): pass"},
        ])
        assert "main.py" in entities.file_paths
        assert "start" in entities.functions
