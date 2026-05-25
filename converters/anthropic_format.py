"""Anthropic ↔ OpenAI format converters.

Pure functions with no server state dependencies.
Extracted from server.py to reduce main file size.
"""

import json
import uuid


def convert_tools_anthropic_to_openai(tools: list) -> list:
    """Anthropic tools format -> OpenAI tools format."""
    openai_tools = []
    for tool in tools:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("input_schema", {})
            }
        })
    return openai_tools


def convert_messages_anthropic_to_openai(messages: list) -> list:
    """Anthropic messages -> OpenAI messages (handles tool_use and tool_result)."""
    openai_msgs = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if isinstance(content, str):
            openai_msgs.append({"role": role, "content": content})
        elif isinstance(content, list):
            text_parts = []
            tool_calls = []
            tool_results = []
            for block in content:
                btype = block.get("type", "")
                if btype == "text":
                    text_parts.append(block.get("text", ""))
                elif btype == "tool_use":
                    tool_calls.append({
                        "id": block["id"],
                        "type": "function",
                        "function": {
                            "name": block["name"],
                            "arguments": json.dumps(block.get("input", {}))
                        }
                    })
                elif btype == "tool_result":
                    tr_content = block.get("content", "")
                    if isinstance(tr_content, list):
                        tr_content = "\n".join(
                            b.get("text", "") for b in tr_content
                            if b.get("type") == "text"
                        )
                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": block.get("tool_use_id", ""),
                        "content": str(tr_content)
                    })
            if tool_calls:
                openai_msgs.append({
                    "role": "assistant",
                    "content": "\n".join(text_parts) if text_parts else None,
                    "tool_calls": tool_calls
                })
            elif tool_results:
                for tr in tool_results:
                    openai_msgs.append(tr)
            else:
                openai_msgs.append({
                    "role": role,
                    "content": "\n".join(text_parts)
                })
    return openai_msgs


def anthropic_system_text(body: dict) -> str:
    system = body.get("system", "")
    if isinstance(system, str):
        return system
    if isinstance(system, list):
        return " ".join(
            block.get("text", "") for block in system
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return ""


def last_openai_user_text(messages: list) -> str:
    for message in reversed(messages):
        if message.get("role") == "user" and isinstance(message.get("content"), str):
            return message["content"]
    return ""


PREFLIGHT_MARKER = "LiMa context preflight:"


def build_lima_context_digest_for_tool_request(
    body: dict,
    openai_msgs: list,
) -> str:
    """Build the LiMa coding digest for Anthropic tool routes."""
    sys_text = anthropic_system_text(body)
    query = last_openai_user_text(openai_msgs)
    try:
        from lima_context import build_context_digest

        return build_context_digest(
            query,
            openai_msgs,
            system_prompt=sys_text,
            ide_source="Claude Code",
        )
    except Exception:
        return ""


def _merge_system_with_digest(sys_text: str, digest: str) -> str:
    if not digest:
        return sys_text
    if digest in sys_text:
        return sys_text
    if sys_text.strip():
        return f"{sys_text.rstrip()}\n\n{digest}".strip()
    return digest


def set_anthropic_system(body: dict, combined: str) -> None:
    """Write merged system text back into an Anthropic request body."""
    if not combined:
        return
    system = body.get("system", "")
    if isinstance(system, list):
        blocks = list(system)
        if blocks and isinstance(blocks[0], dict) and blocks[0].get("type") == "text":
            blocks[0] = {**blocks[0], "text": combined}
        else:
            blocks.insert(0, {"type": "text", "text": combined})
        body["system"] = blocks
    else:
        body["system"] = combined


def inject_anthropic_body_preflight(body: dict, openai_msgs: list) -> None:
    """Inject LiMa context preflight into Anthropic-native tool request bodies."""
    if PREFLIGHT_MARKER in anthropic_system_text(body):
        return
    digest = build_lima_context_digest_for_tool_request(body, openai_msgs)
    combined = _merge_system_with_digest(anthropic_system_text(body), digest)
    set_anthropic_system(body, combined)


def inject_anthropic_context_preflight(openai_msgs: list, body: dict) -> None:
    """Add request-local coding context to Claude Code tool requests (OpenAI msgs)."""
    if openai_msgs and openai_msgs[0].get("role") == "system":
        if PREFLIGHT_MARKER in str(openai_msgs[0].get("content", "")):
            return
    digest = build_lima_context_digest_for_tool_request(body, openai_msgs)
    combined = _merge_system_with_digest(anthropic_system_text(body), digest)
    if not combined:
        return
    if openai_msgs and openai_msgs[0].get("role") == "system":
        openai_msgs[0]["content"] = combined
    else:
        openai_msgs.insert(0, {"role": "system", "content": combined})


def anthropic_text_fallback(model: str, usage: dict = None,
                            detail: str = "") -> dict:
    text = "Tool backend returned an empty or malformed response; please retry."
    if detail:
        text = f"{text} ({detail[:160]})"
    usage = usage or {}
    return {
        "id": f"msg_{uuid.uuid4().hex[:24]}",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": [{"type": "text", "text": text}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0)
        },
    }


def normalize_openai_text(content) -> str:
    if isinstance(content, str):
        return content
    if content is None:
        return ""
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(str(item.get("text", "")))
                elif isinstance(item.get("content"), str):
                    parts.append(item["content"])
            else:
                parts.append(str(item))
        return "".join(parts)
    return str(content)


def convert_response_openai_to_anthropic(openai_response: dict, model: str) -> dict:
    """OpenAI response -> Anthropic response (handles tool_calls)."""
    usage = openai_response.get("usage", {}) if isinstance(openai_response, dict) else {}
    if not isinstance(openai_response, dict):
        return anthropic_text_fallback(model, usage, "non-object response")
    if openai_response.get("error"):
        err = openai_response["error"]
        detail = err.get("message", str(err)) if isinstance(err, dict) else str(err)
        return anthropic_text_fallback(model, usage, detail)

    choices = openai_response.get("choices")
    if not isinstance(choices, list) or not choices:
        return anthropic_text_fallback(model, usage, "missing choices")
    choice = choices[0] if isinstance(choices[0], dict) else {}
    message = choice.get("message") or choice.get("delta") or {}
    if not isinstance(message, dict):
        return anthropic_text_fallback(model, usage, "missing message")

    content = []
    text = normalize_openai_text(message.get("content"))
    if text:
        content.append({"type": "text", "text": text})
    for tc in message.get("tool_calls") or []:
        if not isinstance(tc, dict):
            continue
        fn = tc.get("function") or {}
        if not isinstance(fn, dict) or not fn.get("name"):
            continue
        args_value = fn.get("arguments", "{}")
        if isinstance(args_value, dict):
            args = args_value
        else:
            try:
                args = json.loads(args_value or "{}")
            except (json.JSONDecodeError, TypeError):
                args = {}
        content.append({
            "type": "tool_use",
            "id": tc.get("id", f"toolu_{uuid.uuid4().hex[:24]}"),
            "name": fn["name"],
            "input": args
        })

    if not content:
        return anthropic_text_fallback(model, usage)
    has_tool_use = any(block.get("type") == "tool_use" for block in content)
    finish_reason = choice.get("finish_reason")
    stop_reason = "tool_use" if has_tool_use else (
        "max_tokens" if finish_reason == "length" else "end_turn"
    )
    return {
        "id": f"msg_{uuid.uuid4().hex[:24]}",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": content,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0)
        },
    }
