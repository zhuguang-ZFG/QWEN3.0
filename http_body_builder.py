"""Request body construction extracted from http_request_builder (CQ-014).

Handles: message normalization, system prompt enhancement, tool serialization,
sampling params, session options, prompt caching, doom loop detection, and
output token capping.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time as _time

from opencode_message_normalizer import normalize_messages
from reasoning_variants import apply_variant
from session_options import resolve_session_options

logger = logging.getLogger(__name__)


def build_body(
    backend_cfg: dict,
    messages: list[dict],
    max_tokens: int,
    system_prompt: str = "",
    ide: str = "",
    stream: bool = False,
    tools: list[dict] | None = None,
    reasoning_effort: str | None = None,
    backend_name: str = "",
    sampling: dict | None = None,
) -> bytes:
    """Build the HTTP request body for an LLM API call."""
    model = backend_cfg["model"]
    fmt = backend_cfg["fmt"]

    sys_text = system_prompt
    if ide and ide not in ("unknown", "未知"):
        from prompt_engineering.layers import compose_system_prompt

        scenario = "coding" if fmt != "anthropic" or ide else "chat"
        sys_text = compose_system_prompt(
            ide=ide,
            scenario=scenario,
            code_context=system_prompt if system_prompt else "",
        )

    try:
        from context_pipeline.cache import optimize_for_prefix_cache

        if sys_text and messages:
            sys_text, messages = optimize_for_prefix_cache(sys_text, messages)
    except ImportError:
        logger.debug("prefix cache module not available")
    except Exception as exc:
        logger.warning("prefix cache optimization failed: %s", exc, exc_info=True)

    # M-OC14: model-family-aware system prompt enhancement
    try:
        from opencode_system_prompt import enhance_system_prompt
        sys_text = enhance_system_prompt(sys_text, model, backend_name)
    except ImportError:
        logger.debug("system prompt enhancement module not available")
    except Exception as exc:
        logger.debug("system prompt enhancement failed: %s", exc)

    # M-OC9: filter unsupported media per model capability
    from opencode_media_detect import filter_unsupported_media
    messages = filter_unsupported_media(messages, backend_name, model)

    # Message normalization
    messages = normalize_messages(messages, backend_cfg.get("model", ""))

    # M-OC10: truncate oversized tool outputs
    from opencode_truncate import truncate_tool_results_in_messages
    messages = truncate_tool_results_in_messages(messages)

    # M-OC6: prompt caching
    from opencode_prompt_cache import apply_prompt_caching
    messages = apply_prompt_caching(messages, backend_name, model)

    body = _assemble_body(fmt, backend_cfg, model, max_tokens, sys_text, messages)

    extra = backend_cfg.get("extra_body")
    if extra and isinstance(extra, dict):
        body.update(extra)

    if stream or backend_cfg.get("force_stream_param"):
        body["stream"] = bool(stream)

    if tools:
        tools = _process_tools(tools, backend_name, model, messages)
        body["tools"] = tools
        _maybe_add_invalid_tool(body, tools)

    if reasoning_effort:
        variant_opts = apply_variant(backend_name, model, reasoning_effort)
        if variant_opts:
            for k, v in variant_opts.items():
                body[k] = v
        else:
            body["reasoning_effort"] = reasoning_effort

    for key, value in (sampling or {}).items():
        if value is not None:
            body[key] = value

    # M-OC5: sampling parameters
    from opencode_sampling import resolve_sampling_params
    sampling = resolve_sampling_params(model, backend_name)
    for k, v in sampling.items():
        if k not in body:
            body[k] = v

    # M-OC3: session options
    if _is_ide_backend_session(backend_name, ide):
        session_opts = resolve_session_options(
            backend_name, model, session_id=_mk_session_id(backend_name),
        )
        try:
            from opencode_provider_namespace import build_provider_options_for_body
            from provider_kind import detect_provider_kind
            pk = detect_provider_kind(backend_name, model)
            provider_opts = build_provider_options_for_body(
                session_opts, pk, backend_name, model,
            )
            if provider_opts:
                body["providerOptions"] = provider_opts
        except (ImportError, Exception) as exc:
            logger.debug("provider namespace wrapping failed: %s", exc)

        for k, v in session_opts.items():
            if k not in body:
                body[k] = v

    # M-OC22: doom loop detection
    try:
        from opencode_doom_loop import detect_doom_loop, inject_doom_loop_break
        loop_info = detect_doom_loop(messages)
        if loop_info:
            messages = inject_doom_loop_break(messages, loop_info)
    except ImportError:
        logger.debug("doom loop detection not available")

    # M-OC19: cap max_tokens at OUTPUT_TOKEN_MAX=32000
    try:
        from opencode_output_limit import cap_max_tokens_in_body
        cap_max_tokens_in_body(body, backend_name, model)
    except ImportError:
        logger.debug("output limit module not available")

    return json.dumps(body).encode()


# ── Private helpers ──────────────────────────────────────────────────


def _assemble_body(
    fmt: str, backend_cfg: dict, model: str, max_tokens: int,
    sys_text: str, messages: list[dict],
) -> dict:
    """Assemble the base body dict based on format and backend config."""
    if fmt == "anthropic":
        if backend_cfg.get("no_system"):
            omni_msgs = [
                {
                    "role": m["role"],
                    "content": [{"type": "text", "text": m["content"]}]
                    if isinstance(m["content"], str)
                    else m["content"],
                }
                for m in messages
            ]
            return {"model": model, "max_tokens": max_tokens, "messages": omni_msgs}
        return {
            "model": model, "max_tokens": max_tokens,
            "system": sys_text, "messages": messages,
        }
    if backend_cfg.get("no_system"):
        outgoing = [dict(m) for m in messages]
        if sys_text and outgoing:
            for msg in outgoing:
                if msg.get("role") == "user":
                    content = msg.get("content", "")
                    if isinstance(content, str):
                        msg["content"] = f"{sys_text}\n\n{content}"
                    elif isinstance(content, list):
                        msg["content"] = [{"type": "text", "text": sys_text}] + content
                    break
        return {"model": model, "max_tokens": max_tokens, "messages": outgoing}
    return {
        "model": model, "max_tokens": max_tokens,
        "messages": [{"role": "system", "content": sys_text}] + messages,
    }


def _process_tools(
    tools: list[dict], backend_name: str, model: str, messages: list[dict],
) -> list[dict]:
    """Normalize, sanitize, route, and augment tools for the target backend."""
    # M-OC15: normalize tool JSON schemas
    try:
        from opencode_tool_schema import normalize_tools_schemas
        tools = normalize_tools_schemas(tools)
    except ImportError:
        logger.debug("tool schema normalization not available")

    # M-OC7: sanitize tool schemas for Kimi/Gemini
    from opencode_schema_sanitize import sanitize_tools_for_backend
    tools = sanitize_tools_for_backend(tools, backend_name, model)

    # M-OC16: filter tools by model family
    try:
        from opencode_tool_routing import filter_tools_for_model
        tools = filter_tools_for_model(tools, model, backend_name)
    except ImportError:
        logger.debug("tool model routing not available")

    # M-OC17: Copilot _noop tool workaround
    try:
        from opencode_tool_routing import inject_noop_tool_if_needed
        tools = inject_noop_tool_if_needed(tools, messages, backend_name)
    except ImportError:
        logger.debug("noop tool workaround not available")

    return tools


def _maybe_add_invalid_tool(body: dict, tools: list[dict]) -> None:
    """M-OC20: append invalid tool definition if repair heuristics trigger."""
    try:
        from opencode_tool_repair import should_inject_invalid_tool
        if should_inject_invalid_tool(tools):
            from opencode_tool_repair import get_invalid_tool_definition
            body["tools"] = list(tools) + [get_invalid_tool_definition()]
    except ImportError:
        logger.debug("tool repair module not available")


def _is_ide_backend_session(backend_name: str, ide: str) -> bool:
    """Check if this is an IDE-backed session for session-level optimizations."""
    return bool(ide and ide.lower() in ("opencode",))


def _mk_session_id(backend_name: str) -> str:
    """Deterministic session ID for prompt caching (same backend + same day)."""
    day_key = _time.strftime("%Y%m%d")
    raw = f"{backend_name}:{day_key}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
