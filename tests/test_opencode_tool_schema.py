"""Tests for opencode_tool_schema.py — JSON Schema normalization."""

import math
import pytest
from opencode_tool_schema import (
    normalize_json_schema,
    normalize_tools_schemas,
    MAX_SAFE_INTEGER,
    MIN_SAFE_INTEGER,
)


class TestInlineRefs:
    """$ref inlining tests."""

    def test_basic_ref(self):
        schema = {
            "$defs": {"Address": {"type": "object", "properties": {"street": {"type": "string"}}}},
            "type": "object",
            "properties": {"addr": {"$ref": "#/$defs/Address"}},
        }
        result = normalize_json_schema(schema)
        assert "$ref" not in result["properties"]["addr"]
        assert result["properties"]["addr"]["type"] == "object"

    def test_ref_with_description(self):
        schema = {
            "$defs": {"ID": {"type": "string"}},
            "type": "object",
            "properties": {"id": {"$ref": "#/$defs/ID", "description": "The ID"}},
        }
        result = normalize_json_schema(schema)
        assert result["properties"]["id"]["type"] == "string"
        assert result["properties"]["id"]["description"] == "The ID"


class TestFlattenAllOf:
    """allOf flattening tests."""

    def test_merge_allof(self):
        schema = {
            "allOf": [
                {"type": "object", "properties": {"name": {"type": "string"}}},
                {"properties": {"age": {"type": "integer"}}},
            ],
        }
        result = normalize_json_schema(schema)
        assert "allOf" not in result
        assert "name" in result.get("properties", {})
        assert "age" in result.get("properties", {})

    def test_conflicting_allof_preserved(self):
        schema = {
            "allOf": [
                {"type": "object"},
                {"type": "array"},
            ],
        }
        result = normalize_json_schema(schema)
        # Conflicting types → allOf preserved
        assert "allOf" in result


class TestIntegerBounds:
    """Integer boundary tests."""

    def test_adds_bounds(self):
        schema = {"type": "integer"}
        result = normalize_json_schema(schema)
        assert result["minimum"] == MIN_SAFE_INTEGER
        assert result["maximum"] == MAX_SAFE_INTEGER

    def test_preserves_existing_bounds(self):
        schema = {"type": "integer", "minimum": 0, "maximum": 100}
        result = normalize_json_schema(schema)
        assert result["minimum"] == 0
        assert result["maximum"] == 100

    def test_nested_properties(self):
        schema = {
            "type": "object",
            "properties": {"count": {"type": "integer"}},
        }
        result = normalize_json_schema(schema)
        assert result["properties"]["count"]["minimum"] == MIN_SAFE_INTEGER


class TestStripNullAnyOf:
    """Null anyOf stripping tests."""

    def test_remove_null_from_anyof(self):
        schema = {
            "type": "object",
            "properties": {
                "name": {
                    "anyOf": [{"type": "string"}, {"type": "null"}],
                },
            },
        }
        result = normalize_json_schema(schema)
        prop = result["properties"]["name"]
        # Should be simplified to just string
        assert prop.get("type") == "string"
        assert "anyOf" not in prop

    def test_required_field_preserves_null(self):
        schema = {
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": {
                    "anyOf": [{"type": "string"}, {"type": "null"}],
                },
            },
        }
        result = normalize_json_schema(schema)
        prop = result["properties"]["name"]
        # Required field: null type preserved
        assert "anyOf" in prop


class TestFoldNonfiniteEnum:
    """Non-finite enum folding tests."""

    def test_fold_nan_enum(self):
        schema = {"enum": ["a", "b", float("nan")]}
        result = normalize_json_schema(schema)
        assert "enum" not in result
        assert result.get("type") == "number"

    def test_fold_inf_enum(self):
        schema = {"enum": [1, 2, float("inf")]}
        result = normalize_json_schema(schema)
        assert "enum" not in result

    def test_clean_enum_preserved(self):
        schema = {"enum": ["a", "b", "c"]}
        result = normalize_json_schema(schema)
        assert result["enum"] == ["a", "b", "c"]


class TestFoldEmptyStructUnion:
    """Empty struct union folding tests."""

    def test_object_array_union(self):
        schema = {"anyOf": [{"type": "object"}, {"type": "array"}]}
        result = normalize_json_schema(schema)
        assert result.get("type") == "object"
        assert "anyOf" not in result


class TestNormalizeToolsSchemas:
    """normalize_tools_schemas() batch tests."""

    def test_normalizes_parameters(self):
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "test",
                    "parameters": {
                        "type": "object",
                        "properties": {"count": {"type": "integer"}},
                    },
                },
            },
        ]
        result = normalize_tools_schemas(tools)
        params = result[0]["function"]["parameters"]
        assert params["properties"]["count"]["minimum"] == MIN_SAFE_INTEGER

    def test_no_parameters_unchanged(self):
        tools = [{"type": "function", "function": {"name": "test"}}]
        result = normalize_tools_schemas(tools)
        assert result[0]["function"]["name"] == "test"

    def test_empty_list(self):
        assert normalize_tools_schemas([]) == []
