"""Tool-call repair pipeline: Flatten → Scavenge → Truncation → Storm (MVP)."""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

# DSML / partial XML tool fragments occasionally emitted by open models
_DSML_TOOL_RE = re.compile(
    r"<(?:tool_call|function_call)[^>]*>\s*(\{.*?\})\s*</(?:tool_call|function_call)>",
    re.DOTALL | re.IGNORECASE,
)
_TRUNC_JSON_RE = re.compile(r'\{\s*"name"\s*:\s*"([^"]+)"\s*,\s*"arguments"\s*:\s*(\{.*)', re.DOTALL)
_CODE_FENCE_RE = re.compile(r"```(?:json|tool|javascript)?\s*\n?(.*?)```", re.DOTALL | re.IGNORECASE)


def flatten_tool_payload(data: Any) -> list[dict]:
    """Normalize dict/list/mixed payloads into raw {name, arguments} items."""
    if isinstance(data, dict):
        if "tool_calls" in data and isinstance(data["tool_calls"], list):
            out: list[dict] = []
            for tc in data["tool_calls"]:
                if not isinstance(tc, dict):
                    continue
                fn = tc.get("function") if isinstance(tc.get("function"), dict) else tc
                name = (fn or {}).get("name") or tc.get("name")
                args = (fn or {}).get("arguments") or tc.get("arguments") or {}
                if name:
                    out.append({"name": str(name), "arguments": args})
            return out
        if data.get("name"):
            return [{"name": str(data["name"]), "arguments": data.get("arguments", {})}]
        return []
    if isinstance(data, list):
        items: list[dict] = []
        for entry in data:
            items.extend(flatten_tool_payload(entry))
        return items
    return []


def scavenge_tool_calls(text: str) -> list[dict]:
    """Recover tool JSON from DSML tags, fences, and loose object literals."""
    found: list[dict] = []
    if not text:
        return found

    for match in _DSML_TOOL_RE.finditer(text):
        found.extend(_parse_raw_tool_json(match.group(1)))

    for match in _CODE_FENCE_RE.finditer(text):
        found.extend(_parse_raw_tool_json(match.group(1).strip()))

    # Greedy object scan for name/arguments pairs
    for match in re.finditer(r'\{[^{}]*"name"\s*:\s*"[^"]+"[^{}]*"arguments"\s*:\s*\{[^{}]*\}[^{}]*\}', text):
        found.extend(_parse_raw_tool_json(match.group(0)))

    return _dedupe_tools(found)


def repair_truncated_json(text: str) -> list[dict]:
    """Close truncated {"name":..., "arguments":{...} tool payloads."""
    repaired: list[dict] = []
    for match in _TRUNC_JSON_RE.finditer(text):
        name = match.group(1)
        args_fragment = match.group(2)
        candidate = f'{{"name":"{name}","arguments":{args_fragment}'
        closed = _close_json(candidate)
        if closed:
            repaired.extend(_parse_raw_tool_json(closed))
    return _dedupe_tools(repaired)


def storm_breaker(tool_calls: list[dict], *, max_repeat: int = 3) -> tuple[list[dict], bool]:
    """Drop repeated identical tool calls; return (calls, storm_detected)."""
    if not tool_calls:
        return tool_calls, False
    seen: dict[str, int] = {}
    out: list[dict] = []
    storm = False
    for tc in tool_calls:
        fn = tc.get("function") or {}
        key = f"{fn.get('name')}:{fn.get('arguments')}"
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > max_repeat:
            storm = True
            continue
        out.append(tc)
    return out, storm


def repair_tool_calls_from_text(content: str) -> tuple[str, list[dict] | None, dict[str, Any]]:
    """Run full repair pipeline on model text. Returns (cleaned, tool_calls, meta)."""
    meta: dict[str, Any] = {
        "scavenge": 0,
        "truncation": 0,
        "storm": False,
    }
    if not content:
        return content, None, meta

    raw_items: list[dict] = []
    raw_items.extend(scavenge_tool_calls(content))
    if not raw_items:
        raw_items.extend(repair_truncated_json(content))

    meta["scavenge"] = len(raw_items)
    if not raw_items:
        return content, None, meta

    openai_calls = [_to_openai_tool_call(item) for item in raw_items]
    openai_calls = [c for c in openai_calls if c]
    meta["truncation"] = len(openai_calls)

    openai_calls, storm = storm_breaker(openai_calls)
    meta["storm"] = storm
    if not openai_calls:
        return content, None, meta

    cleaned = content
    for pattern in (_DSML_TOOL_RE, _CODE_FENCE_RE):
        cleaned = pattern.sub("", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    return cleaned, openai_calls, meta


def _parse_raw_tool_json(blob: str) -> list[dict]:
    try:
        data = json.loads(blob)
    except json.JSONDecodeError:
        closed = _close_json(blob)
        if not closed:
            return []
        try:
            data = json.loads(closed)
        except json.JSONDecodeError:
            return []
    return flatten_tool_payload(data)


def _close_json(fragment: str) -> str | None:
    """Best-effort brace balancer for truncated JSON."""
    text = fragment.strip()
    if not text.startswith("{"):
        return None
    depth = 0
    in_str = False
    esc = False
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[: i + 1]
    return text + ("}" * max(depth, 0))


def _to_openai_tool_call(item: dict) -> dict | None:
    name = item.get("name")
    if not name:
        return None
    args = item.get("arguments", {})
    if isinstance(args, dict):
        args_str = json.dumps(args, ensure_ascii=False)
    else:
        args_str = str(args)
    return {
        "id": f"call_{uuid.uuid4().hex[:24]}",
        "type": "function",
        "function": {"name": str(name), "arguments": args_str},
    }


def _dedupe_tools(items: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for item in items:
        key = f"{item.get('name')}:{json.dumps(item.get('arguments', {}), sort_keys=True)}"
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out
