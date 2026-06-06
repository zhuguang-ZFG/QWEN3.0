"""Smoke-test ALL tool_calls backends to find which actually support tool calling.

Tests each backend by sending a simple tool-use prompt via the Anthropic tool
forward pipeline. Reports: working, broken, or text-only (JSON-as-text).
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import health_tracker
from backends_registry import BACKENDS

# Single-turn tool prompt that any model should understand
TOOL_PROMPT = "Use the get_weather tool to check the weather in Beijing. Return the tool call."

TOOL_DEF = {
    "name": "get_weather",
    "description": "Get current weather for a city",
    "input_schema": {
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "City name"},
        },
        "required": ["city"],
    },
}

ANTHROPIC_TOOLS = [TOOL_DEF]
OPENAI_TOOLS = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get current weather for a city",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
    },
}]


def _get_tool_backends() -> list[str]:
    """Get all backends to test: tagged tool_calls + Anthropic-native + GPT-family."""
    candidates = set()
    for name, cfg in BACKENDS.items():
        if health_tracker.is_cooled_down(name):
            continue
        caps = cfg.get("caps", [])
        fmt = cfg.get("fmt", "openai")
        model = cfg.get("model", "").lower()

        # Tagged with tool_calls
        if "tool_calls" in caps:
            candidates.add(name)
        # Anthropic-native backends (all support tools via protocol)
        elif fmt == "anthropic" and "longcat" in name:
            candidates.add(name)
        # GPT-family models (likely support tools even without tag)
        elif "gpt" in model or "claude" in model:
            candidates.add(name)
        # Mistral models (known tool support)
        elif "mistral" in model:
            candidates.add(name)

    tier1 = sorted(candidates)
    native = {"github", "groq", "cerebras", "longcat", "mistral", "chinamobile", "ddg"}
    tier1.sort(key=lambda n: (
        0 if any(p in n for p in native) else 1,
        BACKENDS.get(n, {}).get("timeout", 30),
    ))
    return tier1


async def test_backend_openai(name: str) -> dict:
    """Test a single backend via direct OpenAI-format API call."""
    import httpx
    cfg = BACKENDS[name]
    body = {
        "model": cfg["model"],
        "messages": [{"role": "user", "content": TOOL_PROMPT}],
        "tools": OPENAI_TOOLS,
        "max_tokens": 200,
    }
    headers = {"Content-Type": "application/json"}
    key = cfg.get("key", "")
    if key and key not in ("none", ""):
        headers["Authorization"] = f"Bearer {key}"

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(cfg["url"], headers=headers, json=body)
        if resp.status_code != 200:
            return {"ok": False, "error": f"HTTP {resp.status_code}", "name": name}

        data = resp.json()
        msg = data["choices"][0]["message"]
        tool_calls = msg.get("tool_calls")

        if tool_calls:
            fn = tool_calls[0]["function"]
            return {
                "ok": True,
                "name": name,
                "tool_name": fn["name"],
                "tool_args": fn.get("arguments", "")[:100],
                "native": True,
            }

        # Check if it returned tool call as JSON text (broken model behavior)
        content = msg.get("content", "") or ""
        if '{"name"' in content or '"get_weather"' in content:
            return {
                "ok": True,
                "name": name,
                "tool_name": "get_weather",
                "tool_args": content[:100],
                "native": False,
                "note": "JSON-as-text (not protocol)",
            }

        return {
            "ok": False,
            "name": name,
            "error": "No tool call in response",
            "content_preview": content[:150],
        }
    except Exception as e:
        return {"ok": False, "name": name, "error": str(type(e).__name__) + ": " + str(e)[:100]}


async def test_backend_anthropic(name: str) -> dict:
    """Test an Anthropic-native backend."""
    import httpx
    cfg = BACKENDS[name]
    body = {
        "model": cfg["model"],
        "messages": [{"role": "user", "content": TOOL_PROMPT}],
        "tools": ANTHROPIC_TOOLS,
        "max_tokens": 200,
    }
    headers = {
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01",
    }
    key = cfg.get("key", "")
    if key and key not in ("none", ""):
        if cfg.get("auth") == "bearer":
            headers["Authorization"] = f"Bearer {key}"
        else:
            headers["x-api-key"] = key

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(cfg["url"], headers=headers, json=body)
        if resp.status_code != 200:
            return {"ok": False, "error": f"HTTP {resp.status_code}", "name": name}

        data = resp.json()
        for block in data.get("content", []):
            if block.get("type") == "tool_use":
                return {
                    "ok": True,
                    "name": name,
                    "tool_name": block["name"],
                    "tool_args": json.dumps(block.get("input", {}))[:100],
                    "native": True,
                }
        return {"ok": False, "name": name, "error": "No tool_use in response"}
    except Exception as e:
        return {"ok": False, "name": name, "error": str(type(e).__name__) + ": " + str(e)[:100]}


async def main():
    print("=" * 70)
    print("LiMa Tool Backend Capability Audit")
    print("=" * 70)

    backends = _get_tool_backends()
    print(f"\nTesting {len(backends)} backends with tool_calls cap...\n")

    tasks = []
    for name in backends:
        cfg = BACKENDS[name]
        fmt = cfg.get("fmt", "openai")
        if fmt == "anthropic":
            tasks.append(test_backend_anthropic(name))
        else:
            tasks.append(test_backend_openai(name))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    working_native = []
    working_text = []
    failed = []

    for r in results:
        if isinstance(r, Exception):
            failed.append({"name": "?", "error": str(r)[:80]})
            continue
        if r.get("ok") and r.get("native"):
            working_native.append(r)
        elif r.get("ok") and not r.get("native"):
            working_text.append(r)
        else:
            failed.append(r)

    print(f"{'Backend':<25} {'Status':<12} {'Tool':<15} {'Args'}")
    print("-" * 70)
    for r in working_native:
        print(f"{r['name']:<25} {'NATIVE':<12} {r.get('tool_name','?'):<15} {r.get('tool_args','')[:50]}")
    for r in working_text:
        print(f"{r['name']:<25} {'TEXT-ONLY':<12} {r.get('tool_name','?'):<15} {r.get('note','')}")
    for r in failed:
        err = r.get("error", "?")[:40]
        print(f"{r['name']:<25} {'FAILED':<12} {err}")

    print(f"\n{'='*70}")
    print(f"Native tool call:  {len(working_native)} backends")
    print(f"Text-only (JSON):  {len(working_text)} backends (broken protocol)")
    print(f"Failed/No response:{len(failed)} backends")
    print(f"Total tested:      {len(results)}")

    # Generate recommended pool
    recommended = [r["name"] for r in working_native]
    print(f"\nRecommended tool pool ({len(recommended)}):")
    print(json.dumps(recommended, indent=2))

    if len(working_native) < 3:
        print("\nWARNING: < 3 native tool backends available — vibecode at risk!")
        sys.exit(1)

    print("\nPASS: Sufficient tool backends for vibecode agent loop")


if __name__ == "__main__":
    asyncio.run(main())
