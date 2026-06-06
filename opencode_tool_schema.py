"""opencode_tool_schema.py — JSON Schema 规范化 (LLM 友好格式)。

复刻 OpenCode tool/json-schema.ts (165 行)。

将复杂 JSON Schema 规范化为 LLM 可理解的格式:
  1. $ref 内联解析 — 将 $defs 中的引用直接展开
  2. allOf 展平 — 无冲突的 allOf 合并为单一对象
  3. 整数边界添加 — type: "integer" 无 maximum 时添加安全整数范围
  4. Null anyOf 剥离 — 非 required 字段的 anyOf 中移除 null 类型
  5. 非有限数字 enum 折叠 — NaN/Infinity enum 合并为 number

源码参考:
  - opencode-source/packages/opencode/src/tool/json-schema.ts
"""

from __future__ import annotations

import copy
import logging
import math
from typing import Any

_log = logging.getLogger(__name__)

# ── 安全整数范围 (JavaScript Number.MAX_SAFE_INTEGER) ───────────────────────
MAX_SAFE_INTEGER = 2**53 - 1  # 9007199254740991
MIN_SAFE_INTEGER = -(2**53 - 1)


def normalize_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """将 JSON Schema 规范化为 LLM 友好格式。

    主入口函数，依次执行:
    1. 深拷贝 (不修改原始 schema)
    2. $ref 内联
    3. allOf 展平
    4. 整数边界添加
    5. Null anyOf 剥离
    6. 非有限数字 enum 折叠

    Args:
        schema: 原始 JSON Schema dict。

    Returns:
        规范化后的 schema (新对象)。
    """
    if not schema or not isinstance(schema, dict):
        return schema

    result = copy.deepcopy(schema)
    defs = result.pop("$defs", None) or result.pop("definitions", None) or {}

    result = _inline_refs(result, defs)
    result = _flatten_allof(result)
    result = _add_integer_bounds(result)
    result = _strip_null_anyof(result)
    result = _fold_nonfinite_enum(result)
    result = _fold_empty_struct_union(result)

    return result


def _inline_refs(
    schema: dict[str, Any],
    defs: dict[str, Any],
    _depth: int = 0,
) -> dict[str, Any]:
    """递归展开 $ref 引用 (json-schema.ts L121-144)。"""
    if _depth > 10:
        return schema

    if "$ref" in schema and isinstance(schema["$ref"], str):
        ref_path = schema["$ref"]
        # 只处理 #/$defs/xxx 或 #/definitions/xxx 格式
        parts = ref_path.lstrip("#/").split("/")
        if len(parts) == 2 and parts[0] in ("$defs", "definitions"):
            ref_name = parts[1]
            if ref_name in defs:
                # 展开引用，保留同级的 description 等
                resolved = copy.deepcopy(defs[ref_name])
                for key, val in schema.items():
                    if key != "$ref":
                        resolved[key] = val
                return _inline_refs(resolved, defs, _depth + 1)

    result: dict[str, Any] = {}
    for key, val in schema.items():
        if isinstance(val, dict):
            result[key] = _inline_refs(val, defs, _depth + 1)
        elif isinstance(val, list):
            result[key] = [
                _inline_refs(item, defs, _depth + 1) if isinstance(item, dict) else item
                for item in val
            ]
        else:
            result[key] = val

    return result


def _flatten_allof(schema: dict[str, Any]) -> dict[str, Any]:
    """展平 allOf 为单一对象 (json-schema.ts L78-81)。"""
    if "allOf" in schema and isinstance(schema["allOf"], list):
        all_of = schema["allOf"]
        # 合并所有子 schema，特殊处理 properties 的深层合并
        merged: dict[str, Any] = {}
        can_merge = True
        for sub in all_of:
            if isinstance(sub, dict):
                sub = _flatten_allof(sub)
                for key, val in sub.items():
                    if key in merged:
                        # properties: 深层合并
                        if key == "properties" and isinstance(merged[key], dict) and isinstance(val, dict):
                            merged[key].update(val)
                        # required: 合并列表
                        elif key == "required" and isinstance(merged[key], list) and isinstance(val, list):
                            merged[key] = list(set(merged[key] + val))
                        elif merged[key] != val:
                            can_merge = False
                            break
                    else:
                        merged[key] = val

        if can_merge:
            result = {k: v for k, v in schema.items() if k != "allOf"}
            result.update(merged)
            return result

    # 递归处理子字段
    result: dict[str, Any] = {}
    for key, val in schema.items():
        if isinstance(val, dict):
            result[key] = _flatten_allof(val)
        elif isinstance(val, list):
            result[key] = [
                _flatten_allof(item) if isinstance(item, dict) else item
                for item in val
            ]
        else:
            result[key] = val

    return result


def _add_integer_bounds(schema: dict[str, Any]) -> dict[str, Any]:
    """为 integer 类型添加安全边界 (json-schema.ts L83-85)。"""
    if schema.get("type") == "integer":
        if "minimum" not in schema:
            schema["minimum"] = MIN_SAFE_INTEGER
        if "maximum" not in schema:
            schema["maximum"] = MAX_SAFE_INTEGER

    # 递归处理 properties
    props = schema.get("properties")
    if isinstance(props, dict):
        for key, val in props.items():
            if isinstance(val, dict):
                props[key] = _add_integer_bounds(val)

    # 递归处理 items
    items = schema.get("items")
    if isinstance(items, dict):
        schema["items"] = _add_integer_bounds(items)

    # 递归处理 anyOf / oneOf
    for combo_key in ("anyOf", "oneOf"):
        combo = schema.get(combo_key)
        if isinstance(combo, list):
            schema[combo_key] = [
                _add_integer_bounds(item) if isinstance(item, dict) else item
                for item in combo
            ]

    return schema


def _strip_null_anyof(schema: dict[str, Any]) -> dict[str, Any]:
    """从非 required 字段的 anyOf 中移除 null 类型 (json-schema.ts L51-53)。"""
    props = schema.get("properties")
    required = set(schema.get("required", []))

    if isinstance(props, dict):
        for key, val in props.items():
            if isinstance(val, dict) and key not in required:
                any_of = val.get("anyOf")
                if isinstance(any_of, list):
                    filtered = [
                        item for item in any_of
                        if not (isinstance(item, dict) and item.get("type") == "null")
                    ]
                    if len(filtered) == 1:
                        # 只剩一个类型，直接展开
                        val.update(filtered[0])
                        val.pop("anyOf", None)
                    elif len(filtered) < len(any_of):
                        val["anyOf"] = filtered
                    props[key] = _strip_null_anyof(val)
                else:
                    props[key] = _strip_null_anyof(val)

    # 递归
    items = schema.get("items")
    if isinstance(items, dict):
        schema["items"] = _strip_null_anyof(items)

    return schema


def _fold_nonfinite_enum(schema: dict[str, Any]) -> dict[str, Any]:
    """将包含非有限数字的 enum 折叠为 number 类型 (json-schema.ts L58-65)。"""
    enum = schema.get("enum")
    if isinstance(enum, list):
        has_nonfinite = False
        clean_enum = []
        for val in enum:
            if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                has_nonfinite = True
            else:
                clean_enum.append(val)
        if has_nonfinite:
            schema.pop("enum", None)
            if "type" not in schema:
                schema["type"] = "number"

    # 递归
    props = schema.get("properties")
    if isinstance(props, dict):
        for key, val in props.items():
            if isinstance(val, dict):
                props[key] = _fold_nonfinite_enum(val)

    return schema


def _fold_empty_struct_union(schema: dict[str, Any]) -> dict[str, Any]:
    """将 object|array 联合类型简化 (json-schema.ts L67-69)。"""
    any_of = schema.get("anyOf")
    if isinstance(any_of, list) and len(any_of) == 2:
        types = {
            item.get("type") for item in any_of
            if isinstance(item, dict) and "type" in item
        }
        if types == {"object", "array"}:
            # 简化为 object (更常见)
            schema.pop("anyOf", None)
            schema["type"] = "object"

    return schema


def normalize_tools_schemas(
    tools: list[dict],
) -> list[dict]:
    """批量规范化工具列表中的参数 schema。

    对每个工具的 parameters 字段调用 normalize_json_schema()。

    Args:
        tools: 工具定义列表。

    Returns:
        规范化后的工具列表 (新列表)。
    """
    result = []
    for tool in tools:
        fn = tool.get("function")
        if isinstance(fn, dict) and "parameters" in fn:
            new_fn = dict(fn)
            new_fn["parameters"] = normalize_json_schema(fn["parameters"])
            tool = {**tool, "function": new_fn}
        result.append(tool)
    return result
