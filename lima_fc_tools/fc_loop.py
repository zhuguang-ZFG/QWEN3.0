"""Function Calling execution loop for Telegram tools."""

import json
from typing import Any

from .registry import TOOLS, execute_tool

FC_BACKENDS = [
    "github_gpt4o",
    "github_gpt5",
    "github_o4_mini",
    "groq_llama70b",
    "groq_qwen32b",
    "google_gemini3",
    "google_flash",
    # M6: deepseek_free deleted
    "mistral_large",
    "cf_kimi_k26",
    "cf_qwen3_30b",
]

MAX_TOOL_ROUNDS = 5


def _pick_backend() -> str:
    import health_tracker

    health_map = health_tracker.get_health_map()
    for backend in FC_BACKENDS:
        if health_map.get(backend) != "dead":
            return backend
    return FC_BACKENDS[0]


async def run_fc_loop(messages: list[dict[str, Any]], call_fn, backend: str = "") -> dict[str, Any]:
    """Run model tool calls until the model stops requesting tools."""
    if not backend:
        backend = _pick_backend()

    tool_calls_made = []

    for _round_num in range(MAX_TOOL_ROUNDS):
        result = call_fn(backend, messages, 4096, tools=TOOLS)
        if isinstance(result, dict):
            answer = result.get("answer", "")
            tool_calls = result.get("tool_calls", [])
        else:
            answer = getattr(result, "answer", str(result))
            tool_calls = getattr(result, "tool_calls", [])

        if not tool_calls:
            return {"answer": answer, "tool_calls_made": tool_calls_made, "backend": backend}

        messages.append({"role": "assistant", "content": answer, "tool_calls": tool_calls})

        for call in tool_calls:
            fn_name = call.get("function", {}).get("name", "")
            fn_args_raw = call.get("function", {}).get("arguments", "{}")
            try:
                fn_args = json.loads(fn_args_raw) if isinstance(fn_args_raw, str) else fn_args_raw
            except json.JSONDecodeError:
                fn_args = {}

            tool_result = await execute_tool(fn_name, fn_args)
            tool_calls_made.append({"tool": fn_name, "args": fn_args, "result": tool_result[:200]})

            messages.append({
                "role": "tool",
                "tool_call_id": call.get("id", ""),
                "name": fn_name,
                "content": tool_result,
            })

    final = call_fn(backend, messages, 4096)
    answer = final.get("answer", "") if isinstance(final, dict) else str(final)
    return {"answer": answer, "tool_calls_made": tool_calls_made, "backend": backend}
