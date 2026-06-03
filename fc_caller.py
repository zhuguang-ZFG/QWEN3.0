"""Function Calling integration used by Telegram chat commands."""
import asyncio
import json
import logging

import http_caller
import health_tracker
import tool_dispatcher
from backends import BACKENDS

log = logging.getLogger(__name__)

FC_BACKENDS = [
    "github_gpt4o", "github_gpt5", "github_o4_mini",
    "groq_llama70b", "groq_qwen32b",
    "google_gemini3", "google_flash",
    # M6: deepseek_free deleted
    "mistral_large", "mistral_small",
    "cf_kimi_k26", "cf_qwen3_30b",
    "scnet_ds_flash", "scnet_qwen30b",
]

MAX_ROUNDS = 4


def _pick_fc_backend() -> str:
    hmap = health_tracker.get_health_map()
    for b in FC_BACKENDS:
        if b in BACKENDS and hmap.get(b) != "dead":
            return b
    return FC_BACKENDS[0]


def _call_with_tools(backend: str, messages: list, tools: list) -> dict:
    """Call a backend with OpenAI-compatible tool definitions."""
    cfg = BACKENDS.get(backend, {})
    body = {
        "model": cfg.get("model", ""),
        "messages": messages,
        "tools": tools,
        "max_tokens": 4096,
    }
    payload = json.dumps(body, ensure_ascii=False).encode()
    return http_caller.call_raw(backend, payload)


def _extract_fc_response(data: dict) -> tuple[str, list]:
    """Extract assistant text and tool calls from a backend response."""
    msg = data.get("choices", [{}])[0].get("message", {})
    content = msg.get("content", "") or ""
    tool_calls = msg.get("tool_calls", [])
    return content, tool_calls


async def _execute_single_tool(tc: dict) -> dict:
    """Execute a single tool call and return result with metadata."""
    fn = tc.get("function", {})
    fn_name = fn.get("name", "")
    try:
        fn_args = json.loads(fn.get("arguments", "{}"))
    except json.JSONDecodeError:
        fn_args = {}
    
    result = await tool_dispatcher.execute_tool(fn_name, fn_args)
    return {
        "tool_call_id": tc.get("id", ""),
        "name": fn_name,
        "content": result[:3000],
    }


async def _execute_tools_parallel(tool_calls: list[dict]) -> list[dict]:
    """Execute multiple tool calls in parallel while preserving order."""
    if not tool_calls:
        return []
    
    # Execute all tool calls concurrently
    tasks = [_execute_single_tool(tc) for tc in tool_calls]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Handle any exceptions and preserve order
    final_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            fn = tool_calls[i].get("function", {})
            final_results.append({
                "tool_call_id": tool_calls[i].get("id", ""),
                "name": fn.get("name", ""),
                "content": f"Error: {str(result)[:200]}",
            })
        else:
            final_results.append(result)
    
    return final_results


async def chat_with_tools(messages: list[dict], system_prompt: str = "") -> dict:
    """Run a bounded Function Calling chat loop."""
    backend = _pick_fc_backend()
    tools = tool_dispatcher.get_tools_schema()
    tools_used = []

    fc_messages = []
    if system_prompt:
        fc_messages.append({"role": "system", "content": system_prompt})
    fc_messages.extend(messages)

    for _ in range(MAX_ROUNDS):
        try:
            data = _call_with_tools(backend, fc_messages, tools)
        except Exception as e:
            log.warning(f"FC call failed on {backend}: {e}")
            return {"answer": "", "tools_used": [], "backend": backend, "error": str(e)}

        content, tool_calls = _extract_fc_response(data)

        if not tool_calls:
            return {"answer": content, "tools_used": tools_used, "backend": backend}

        fc_messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})

        # Execute tool calls in parallel
        tool_results = await _execute_tools_parallel(tool_calls)
        
        # Add results to messages and track tool usage
        for result in tool_results:
            tools_used.append(result["name"])
            fc_messages.append({
                "role": "tool",
                "tool_call_id": result["tool_call_id"],
                "name": result["name"],
                "content": result["content"],
            })

    try:
        data = _call_with_tools(backend, fc_messages, [])
        content, _ = _extract_fc_response(data)
        return {"answer": content, "tools_used": tools_used, "backend": backend}
    except Exception as e:
        return {"answer": "", "tools_used": tools_used, "backend": backend, "error": str(e)}
