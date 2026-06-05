"""opencode_schema_sanitize.py — Tool JSON schema sanitization per provider.

复刻 OpenCode transform.ts schema() (L1254-1371)。
不同后端对 JSON schema 有不同的格式要求:
  - Moonshot/Kimi: 移除 $ref 兄弟关键词，扁平化 tuple items
  - Google/Gemini: integer enum → string enum，清理非 object 的 properties/required

不合规的 schema 会导致 Kimi/Gemini 返回 400 错误。

核心功能:
  1. sanitize_tool_schema() — 对单个 tool schema 做后端特定清洗
  2. sanitize_tools_for_backend() — 对 tools 列表中所有 tool 做批量清洗
"""

from __future__ import annotations

import copy
import logging
from typing import Any

from provider_kind import detect_provider_kind

_log = logging.getLogger(__name__)


def sanitize_tool_schema(
    schema: dict[str, Any],
    backend_name: str,
    model_id: str,
    provider_kind: str = "",
) -> dict[str, Any]:
    """Sanitize a single tool parameter JSON schema for the target backend.

    Ported from transform.ts schema() (L1254-1371).

    Args:
        schema: JSON schema dict (will not be mutated).
        backend_name: Backend identifier.
        model_id: Model identifier.
        provider_kind: Optional pre-computed provider kind.

    Returns:
        Sanitized schema (may be same object if no changes needed).
    """
    pk = provider_kind or detect_provider_kind(backend_name, model_id)
    mid = model_id.lower()

    result = schema

    # ── Moonshot / Kimi sanitization (transform.ts:1273-1289) ────────────
    if pk == "kimi" or "kimi" in mid or "moonshot" in backend_name.lower():
        sanitized = _sanitize_moonshot(result)
        if isinstance(sanitized, dict):
            result = sanitized

    # ── Google / Gemini sanitization (transform.ts:1292-1368) ────────────
    if pk == "google" or "gemini" in mid:
        result = _sanitize_gemini(result)

    return result


def sanitize_tools_for_backend(
    tools: list[dict],
    backend_name: str,
    model_id: str,
    provider_kind: str = "",
) -> list[dict]:
    """Sanitize all tool schemas in a tools list for the target backend.

    Args:
        tools: OpenAI-format tools list (each has 'function.parameters').
        backend_name: Backend identifier.
        model_id: Model identifier.
        provider_kind: Optional pre-computed provider kind.

    Returns:
        New tools list with sanitized schemas. Original is not mutated.
    """
    pk = provider_kind or detect_provider_kind(backend_name, model_id)
    mid = model_id.lower()

    # Quick check: skip if no sanitization needed
    needs_kimi = pk == "kimi" or "kimi" in mid or "moonshot" in backend_name.lower()
    needs_gemini = pk == "google" or "gemini" in mid
    if not needs_kimi and not needs_gemini:
        return tools

    result = []
    for tool in tools:
        fn = tool.get("function")
        if not fn or "parameters" not in fn:
            result.append(tool)
            continue

        params = fn["parameters"]
        sanitized = sanitize_tool_schema(params, backend_name, model_id, pk)
        if sanitized is params:
            result.append(tool)
        else:
            new_fn = {**fn, "parameters": sanitized}
            result.append({**tool, "function": new_fn})

    _log.debug(
        "Sanitized %d tool schemas for backend=%s model=%s",
        len(result), backend_name, model_id,
    )
    return result


# ── Moonshot / Kimi sanitization ────────────────────────────────────────────


def _sanitize_moonshot(obj: Any) -> Any:
    """Recursively sanitize Moonshot/Kimi schema.

    - Remove sibling keys of $ref (Moonshot expands $ref before validation)
    - Flatten tuple-style items arrays to single schema
    """
    if obj is None or not isinstance(obj, (dict, list)):
        return obj

    if isinstance(obj, list):
        return [_sanitize_moonshot(item) for item in obj]

    # dict
    if "$ref" in obj and isinstance(obj.get("$ref"), str):
        # Moonshot rejects sibling keywords on $ref nodes
        return {"$ref": obj["$ref"]}

    result = {}
    for key, value in obj.items():
        result[key] = _sanitize_moonshot(value)

    # Flatten tuple-style items array to single schema
    if isinstance(result.get("items"), list):
        items_list = result["items"]
        result["items"] = items_list[0] if items_list else {}

    return result


# ── Google / Gemini sanitization ─────────────────────────────────────────────


def _is_plain_object(node: Any) -> bool:
    """Check if node is a plain dict (not list, not None)."""
    return isinstance(node, dict)


def _has_combiner(node: Any) -> bool:
    """Check if schema node has anyOf/oneOf/allOf combiners."""
    if not _is_plain_object(node):
        return False
    return any(
        isinstance(node.get(k), list)
        for k in ("anyOf", "oneOf", "allOf")
    )


_SCHEMA_INTENT_KEYS = frozenset({
    "type", "properties", "items", "prefixItems", "enum", "const",
    "$ref", "additionalProperties", "patternProperties", "required",
    "not", "if", "then", "else",
})


def _has_schema_intent(node: Any) -> bool:
    """Check if a schema node has any meaningful schema keywords."""
    if not _is_plain_object(node):
        return False
    if _has_combiner(node):
        return True
    return any(key in node for key in _SCHEMA_INTENT_KEYS)


def _sanitize_gemini(obj: Any) -> Any:
    """Recursively sanitize Gemini schema.

    - Convert integer/number enums to string enums
    - Filter required to only existing properties
    - Ensure empty array items have type="string"
    - Remove properties/required from non-object types
    """
    if obj is None or not isinstance(obj, (dict, list)):
        return obj

    if isinstance(obj, list):
        return [_sanitize_gemini(item) for item in obj]

    result: dict[str, Any] = {}
    for key, value in obj.items():
        if key == "enum" and isinstance(value, list):
            # Convert all enum values to strings
            result[key] = [str(v) for v in value]
            # If type is integer/number with enum, change to string
            if result.get("type") in ("integer", "number"):
                result["type"] = "string"
        elif isinstance(value, (dict, list)) and value is not None:
            result[key] = _sanitize_gemini(value)
        else:
            result[key] = value

    # Filter required array to only include fields that exist in properties
    if (
        result.get("type") == "object"
        and isinstance(result.get("properties"), dict)
        and isinstance(result.get("required"), list)
    ):
        props = result["properties"]
        result["required"] = [f for f in result["required"] if f in props]

    # Ensure array items has type when items is empty schema
    if result.get("type") == "array" and not _has_combiner(result):
        items = result.get("items")
        if items is None:
            result["items"] = {}
            items = result["items"]
        if _is_plain_object(items) and not _has_schema_intent(items):
            items["type"] = "string"

    # Remove properties/required from non-object types (Gemini rejects these)
    if result.get("type") and result["type"] != "object" and not _has_combiner(result):
        result.pop("properties", None)
        result.pop("required", None)

    return result
