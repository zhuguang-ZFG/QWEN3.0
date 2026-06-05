"""Tests for opencode_schema_sanitize.py — Kimi/Gemini schema sanitization."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from opencode_schema_sanitize import (
    sanitize_tool_schema,
    sanitize_tools_for_backend,
    _sanitize_moonshot,
    _sanitize_gemini,
)


class TestMoonshotSanitize:
    def test_ref_removes_siblings(self):
        schema = {"$ref": "#/defs/Foo", "description": "A foo"}
        result = _sanitize_moonshot(schema)
        assert result == {"$ref": "#/defs/Foo"}
        assert "description" not in result

    def test_tuple_items_flattened(self):
        schema = {
            "type": "array",
            "items": [{"type": "string"}, {"type": "number"}],
        }
        result = _sanitize_moonshot(schema)
        assert result["items"] == {"type": "string"}

    def test_empty_tuple_items(self):
        schema = {"type": "array", "items": []}
        result = _sanitize_moonshot(schema)
        assert result["items"] == {}

    def test_nested_ref(self):
        schema = {
            "type": "object",
            "properties": {
                "foo": {"$ref": "#/defs/Foo", "title": "Foo Field"},
            },
        }
        result = _sanitize_moonshot(schema)
        assert result["properties"]["foo"] == {"$ref": "#/defs/Foo"}

    def test_no_ref_unchanged(self):
        schema = {"type": "object", "properties": {"a": {"type": "string"}}}
        result = _sanitize_moonshot(schema)
        assert result == schema


class TestGeminiSanitize:
    def test_integer_enum_to_string(self):
        schema = {"type": "integer", "enum": [1, 2, 3]}
        result = _sanitize_gemini(schema)
        assert result["type"] == "string"
        assert result["enum"] == ["1", "2", "3"]

    def test_number_enum_to_string(self):
        schema = {"type": "number", "enum": [1.5, 2.5]}
        result = _sanitize_gemini(schema)
        assert result["type"] == "string"
        assert result["enum"] == ["1.5", "2.5"]

    def test_filter_required_to_properties(self):
        schema = {
            "type": "object",
            "properties": {"a": {"type": "string"}},
            "required": ["a", "b"],  # "b" not in properties
        }
        result = _sanitize_gemini(schema)
        assert result["required"] == ["a"]

    def test_array_empty_items_gets_string_type(self):
        schema = {"type": "array", "items": {}}
        result = _sanitize_gemini(schema)
        assert result["items"]["type"] == "string"

    def test_array_null_items_gets_empty_with_string(self):
        schema = {"type": "array"}
        result = _sanitize_gemini(schema)
        assert result["items"] == {"type": "string"}

    def test_non_object_removes_properties(self):
        schema = {
            "type": "string",
            "properties": {"a": {"type": "string"}},
            "required": ["a"],
        }
        result = _sanitize_gemini(schema)
        assert "properties" not in result
        assert "required" not in result

    def test_object_keeps_properties(self):
        schema = {
            "type": "object",
            "properties": {"a": {"type": "string"}},
            "required": ["a"],
        }
        result = _sanitize_gemini(schema)
        assert "properties" in result
        assert "required" in result

    def test_combiner_preserved(self):
        schema = {
            "anyOf": [{"type": "string"}, {"type": "null"}],
            "properties": {"a": {"type": "string"}},
        }
        result = _sanitize_gemini(schema)
        assert "anyOf" in result
        # Combiner means properties/required are not removed
        assert "properties" in result


class TestSanitizeToolSchema:
    def test_kimi_provider(self):
        schema = {"type": "object", "properties": {"ref_field": {"$ref": "#/defs/X", "description": "desc"}}}
        result = sanitize_tool_schema(schema, "kimi_api", "kimi-k2")
        assert result["properties"]["ref_field"] == {"$ref": "#/defs/X"}

    def test_gemini_provider(self):
        schema = {"type": "object", "properties": {"count": {"type": "integer", "enum": [1, 2, 3]}}}
        result = sanitize_tool_schema(schema, "google_gemini", "gemini-2.5-pro")
        assert result["properties"]["count"]["type"] == "string"
        assert result["properties"]["count"]["enum"] == ["1", "2", "3"]

    def test_openai_no_change(self):
        schema = {"type": "object", "properties": {"a": {"type": "string"}}}
        result = sanitize_tool_schema(schema, "openai", "gpt-4o")
        assert result is schema  # Same object, no changes


class TestSanitizeToolsForBackend:
    def test_batch_sanitization(self):
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "test_tool",
                    "parameters": {"type": "integer", "enum": [1, 2]},
                },
            },
        ]
        result = sanitize_tools_for_backend(tools, "google_gemini", "gemini-2.5-pro")
        params = result[0]["function"]["parameters"]
        assert params["type"] == "string"
        assert params["enum"] == ["1", "2"]

    def test_no_tools_function_key(self):
        tools = [{"type": "custom", "data": {}}]
        result = sanitize_tools_for_backend(tools, "google_gemini", "gemini-2.5-pro")
        assert result == tools

    def test_skip_for_unsupported_backend(self):
        tools = [
            {"type": "function", "function": {"name": "t", "parameters": {"type": "integer", "enum": [1]}}},
        ]
        result = sanitize_tools_for_backend(tools, "openai", "gpt-4o")
        assert result is tools  # Same list, no changes
