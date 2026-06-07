"""Hermes Agent bridge — LiMa ↔ Hermes integration layer.

Mode 2 (LiMa → Hermes): OpenAI SDK client for local LiMa API, with structured task dispatch.
Mode 3 (Bidirectional): Agent task classification, streaming support, tool-call extraction.

Since `hermes -z` subprocess is unreliable in non-interactive environments,
this module uses the OpenAI SDK to call LiMa's own API — benefiting from LiMa's
289-backend smart routing — while Hermes Agent independently uses LiMa as its
custom:lima provider.

The bridge provides:
- call_lima(): Simple OpenAI SDK call to local LiMa API.
- call_lima_stream(): Streaming OpenAI SDK call (SSE generator).
- call_lima_structured(): Structured task dispatch with task-type prefixes.
- call_hermes_agent(): Hermes Agent integration for autonomous execution.
- extract_tool_calls(): Parse tool_calls from OpenAI response.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from collections.abc import Generator
from typing import Any

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────
LIMA_BASE_URL = os.environ.get("LIMA_BASE_URL", "http://127.0.0.1:8080/v1")
LIMA_API_KEY = os.environ.get("LIMA_API_KEY", "")
LIMA_MODEL = os.environ.get("LIMA_MODEL", "lima-1.3")
LIMA_TIMEOUT = int(os.environ.get("LIMA_TIMEOUT", "120"))

# Hermes Agent integration (future)
HERMES_ENABLED = os.environ.get("HERMES_AGENT_ENABLED", "0") == "1"


def _get_client():
    """Lazy-init OpenAI client pointing at local LiMa."""
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("openai package is required for hermes_bridge")

    api_key = LIMA_API_KEY
    if not api_key:
        # Fallback: read from LiMa .env
        env_path = os.environ.get("LIMA_ENV_PATH", "/opt/lima-router/.env")
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.startswith("LIMA_API_KEY="):
                        api_key = line.strip().split("=", 1)[1]
                        break

    if not api_key:
        raise RuntimeError("LIMA_API_KEY not found in env or .env file")

    return OpenAI(base_url=LIMA_BASE_URL, api_key=api_key, timeout=LIMA_TIMEOUT)


# ── Public API ──────────────────────────────────────────────────


def call_lima(
    messages: list[dict],
    *,
    model: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.7,
    timeout: int | None = None,
) -> tuple[str, float]:
    """Call LiMa API via OpenAI SDK and return (response_text, latency_ms).

    This uses LiMa's full 289-backend routing pipeline.

    Args:
        messages: OpenAI-format messages list.
        model: Model name (default: LIMA_MODEL env or lima-1.3).
        max_tokens: Max output tokens.
        temperature: Sampling temperature.
        timeout: Request timeout in seconds.

    Returns:
        Tuple of (response_text, latency_ms).
    """
    client = _get_client()
    model = model or LIMA_MODEL
    timeout = timeout or LIMA_TIMEOUT

    logger.debug("hermes_bridge: calling lima model=%s", model)
    t0 = time.time()

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
        )
    except Exception:
        logger.exception("hermes_bridge: lima call failed")
        raise

    latency_ms = (time.time() - t0) * 1000
    content = resp.choices[0].message.content or ""

    logger.info(
        "hermes_bridge: success latency=%.0fms tokens=%s",
        latency_ms,
        resp.usage.total_tokens if resp.usage else "N/A",
    )
    return content, latency_ms


def call_lima_stream(
    messages: list[dict],
    *,
    model: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.7,
    timeout: int | None = None,
) -> Generator[str, None, None]:
    """Call LiMa API with streaming via OpenAI SDK.

    Yields content chunks as they arrive (SSE delta format).
    Use this for real-time streaming output in chat completions.

    Args:
        messages: OpenAI-format messages list.
        model: Model name (default: LIMA_MODEL env or lima-1.3).
        max_tokens: Max output tokens.
        temperature: Sampling temperature.
        timeout: Request timeout in seconds.

    Yields:
        Content string chunks as they stream in.
    """
    client = _get_client()
    model = model or LIMA_MODEL
    timeout = timeout or LIMA_TIMEOUT

    logger.debug("hermes_bridge: streaming lima model=%s", model)
    t0 = time.time()

    try:
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
            stream=True,
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except Exception:
        logger.exception("hermes_bridge: stream call failed")
        raise

    latency_ms = (time.time() - t0) * 1000
    logger.info("hermes_bridge: stream complete latency=%.0fms", latency_ms)


def extract_tool_calls(response_text: str) -> list[dict[str, Any]]:
    """Extract tool/function calls from a response text.

    Looks for:
    1. JSON code blocks with function_call / tool_calls structure
    2. Inline JSON function_call patterns
    3. Markdown code blocks labeled as tool_call or function_call

    Args:
        response_text: Raw response from the model.

    Returns:
        List of tool call dicts with keys: 'name', 'arguments', 'id'.
        Empty list if no tool calls detected.
    """
    tools: list[dict[str, Any]] = []

    # Pattern 1: JSON code blocks with tool_calls
    json_blocks = re.findall(
        r'```(?:json|tool_call|function_call)?\s*\n?(.*?)\n?```',
        response_text, re.DOTALL | re.IGNORECASE,
    )
    for block in json_blocks:
        try:
            data = json.loads(block.strip())
            if isinstance(data, dict):
                # Direct function_call format
                if "name" in data and "arguments" in data:
                    tools.append({
                        "id": f"call_{len(tools)}",
                        "name": data["name"],
                        "arguments": json.dumps(data["arguments"], ensure_ascii=False)
                        if isinstance(data["arguments"], dict) else str(data["arguments"]),
                    })
                # Nested tool_calls format
                if "tool_calls" in data:
                    for tc in data["tool_calls"]:
                        if isinstance(tc, dict):
                            args = tc.get("arguments", {})
                            tools.append({
                                "id": tc.get("id", f"call_{len(tools)}"),
                                "name": tc.get("name", "unknown"),
                                "arguments": json.dumps(args, ensure_ascii=False)
                                if isinstance(args, dict) else str(args),
                            })
        except (json.JSONDecodeError, TypeError):
            continue

    # Pattern 2: Inline function_call JSON (non-code-block)
    inline_pattern = r'\{\s*"(?:name|function_name)"\s*:\s*"([^"]+)"\s*,\s*"arguments"\s*:\s*(\{[^}]+\})'
    for match in re.finditer(inline_pattern, response_text):
        name, args_str = match.group(1), match.group(2)
        try:
            args = json.loads(args_str)
            tools.append({
                "id": f"call_{len(tools)}",
                "name": name,
                "arguments": json.dumps(args, ensure_ascii=False),
            })
        except json.JSONDecodeError:
            tools.append({
                "id": f"call_{len(tools)}",
                "name": name,
                "arguments": args_str,
            })

    return tools


def _detect_tool_request(messages: list[dict]) -> bool:
    """Check if messages contain tool call requests from user side."""
    for m in messages:
        if isinstance(m, dict) and m.get("role") == "tool":
            return True
        if isinstance(m, dict) and m.get("role") == "assistant":
            if m.get("tool_calls"):
                return True
    return False


def call_lima_structured(
    task_type: str,
    prompt: str,
    *,
    context: dict | None = None,
    system_prompt: str = "",
    **kwargs,
) -> dict:
    """Call LiMa for a structured task with type-specific prompting (Mode 2/3).

    Args:
        task_type: One of 'code_exec', 'file_ops', 'browser', 'research', 'chat'.
        prompt: The user prompt.
        context: Optional context dict.
        system_prompt: Optional system prompt.
        **kwargs: Passed through to call_lima().

    Returns:
        Dict with keys: 'response', 'task_type', 'latency_ms', 'model'.
    """
    task_prefixes = {
        "code_exec": "[TASK: Code Execution]\nWrite and execute code to accomplish the following:\n",
        "file_ops": "[TASK: File Operations]\nRead, write, or modify files as needed:\n",
        "browser": "[TASK: Browser]\nUse browser tools to accomplish:\n",
        "research": "[TASK: Research]\nResearch and provide comprehensive information about:\n",
        "chat": "",
    }

    full_prompt = task_prefixes.get(task_type, "") + prompt

    if context:
        ctx_str = "\n".join(f"  {k}: {v}" for k, v in context.items() if v)
        if ctx_str:
            full_prompt += f"\n\nContext:\n{ctx_str}"

    messages = [{"role": "user", "content": full_prompt}]
    if system_prompt:
        messages.insert(0, {"role": "system", "content": system_prompt})

    response, latency_ms = call_lima(messages, **kwargs)

    return {
        "response": response,
        "task_type": task_type,
        "latency_ms": round(latency_ms, 0),
        "model": kwargs.get("model", LIMA_MODEL),
    }


def call_hermes_agent(
    prompt: str,
    *,
    task_type: str = "chat",
    extract_tools: bool = False,
    **kwargs,
) -> dict:
    """Call Hermes Agent for autonomous task execution (Mode 3).

    Uses Hermes Gateway API when available (HERMES_AGENT_ENABLED=1),
    falling back to call_lima_structured() (OpenAI SDK via LiMa routing).

    Args:
        prompt: The user prompt.
        task_type: One of 'code_exec', 'file_ops', 'browser', 'research', 'chat'.
        extract_tools: If True, parse tool calls from response.
        **kwargs: Passed through to backend.

    Returns:
        Dict with keys: 'response', 'task_type', 'latency_ms', 'model',
        and optionally 'tool_calls', 'task_id', 'steps', 'success' if Gateway used.
    """
    # Try Hermes Gateway first (real agent execution)
    if HERMES_ENABLED:
        try:
            from hermes_gateway import send_agent_task, _check_gateway  # isort: skip (optional dep)

            if _check_gateway():
                result = send_agent_task(
                    prompt, task_type=task_type, **kwargs
                )
                if result.get("success"):
                    logger.info(
                        "hermes_agent: gateway task complete steps=%d",
                        result.get("steps", 0),
                    )
                if extract_tools and not result.get("tool_calls"):
                    tools = extract_tool_calls(result.get("response", ""))
                    if tools:
                        result["tool_calls"] = tools
                return result
            else:
                logger.debug("hermes_agent: gateway health check failed, falling back")
        except (ImportError, RuntimeError) as e:
            logger.debug("hermes_agent: gateway not available (%s), falling back", e)

    # Fallback: structured lima call (current behavior)
    result = call_lima_structured(task_type, prompt, **kwargs)

    if extract_tools:
        tools = extract_tool_calls(result.get("response", ""))
        if tools:
            result["tool_calls"] = tools
            logger.info("hermes_agent: extracted %d tool calls", len(tools))

    return result


# ── Direct test ─────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")

    prompt = sys.argv[1] if len(sys.argv) > 1 else "say OK in one word"
    try:
        response, latency = call_lima([{"role": "user", "content": prompt}])
        print(f"[OK] latency={latency:.0f}ms")
        print(response)
    except Exception as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
