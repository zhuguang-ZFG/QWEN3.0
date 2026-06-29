"""Request body builders."""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _extract_user_query(messages: list[dict] | None) -> str:
    if not messages:
        return ""
    last = messages[-1]
    if not isinstance(last, dict):
        return ""
    content = last.get("content", "")
    if isinstance(content, list):
        return " ".join(
            block.get("text", "") for block in content if isinstance(block, dict) and block.get("type") == "text"
        ).strip()
    return str(content or "").strip()


def _enrich_system_prompt(
    system_prompt: str,
    ide: str,
    fmt: str,
    messages: list[dict] | None = None,
) -> str:
    """Apply IDE-aware system prompt composition."""
    if not ide or ide in ("unknown", "\u672a\u77e5"):
        return system_prompt
    from prompt_engineering.device_intent_prompt import merge_device_intent_system_prompt

    query = _extract_user_query(messages)
    merged = merge_device_intent_system_prompt(query, system_prompt, ide_source=ide)
    if merged != system_prompt:
        return merged

    from prompt_engineering.layers import compose_system_prompt

    # v3.0 编码能力退役：所有请求统一使用 chat 场景模板
    return compose_system_prompt(
        ide=ide,
        scenario="chat",
        code_context=system_prompt if system_prompt else "",
    )


def _apply_prefix_cache(sys_text: str, messages: list[dict]) -> tuple[str, list[dict]]:
    """Apply prefix cache optimization if available."""
    try:
        from context_pipeline.cache import optimize_for_prefix_cache

        if sys_text and messages:
            sys_text, messages = optimize_for_prefix_cache(sys_text, messages)
    except ImportError:
        # Module absent is the normal case on many deployments; avoid logging it
        # on every request, which floods the disk and stalls the event loop.
        logger.debug("context_pipeline.cache.optimize_for_prefix_cache not available; prefix cache disabled")
    except Exception as exc:
        logger.warning("prefix cache optimization failed: %s", exc, exc_info=True)
    return sys_text, messages


def _build_anthropic_body(cfg: dict, model: str, max_tokens: int, sys_text: str, messages: list[dict]) -> dict:
    """Build request body in Anthropic format."""
    if cfg.get("no_system"):
        omni_msgs = [
            {
                "role": m["role"],
                "content": [{"type": "text", "text": m["content"]}] if isinstance(m["content"], str) else m["content"],
            }
            for m in messages
        ]
        return {"model": model, "max_tokens": max_tokens, "messages": omni_msgs}
    return {"model": model, "max_tokens": max_tokens, "system": sys_text, "messages": messages}


def _build_openai_body(cfg: dict, model: str, max_tokens: int, sys_text: str, messages: list[dict]) -> dict:
    """Build request body in OpenAI-compatible format."""
    if cfg.get("no_system"):
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
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "system", "content": sys_text}] + messages,
    }


def _build_body(
    backend_cfg: dict,
    messages: list[dict],
    max_tokens: int,
    system_prompt: str = "",
    ide: str = "",
    stream: bool = False,
    tools: list[dict] | None = None,
) -> bytes:
    model = backend_cfg["model"]
    fmt = backend_cfg["fmt"]

    sys_text = _enrich_system_prompt(system_prompt, ide, fmt, messages)
    sys_text, messages = _apply_prefix_cache(sys_text, messages)

    if fmt == "anthropic":
        body = _build_anthropic_body(backend_cfg, model, max_tokens, sys_text, messages)
    else:
        body = _build_openai_body(backend_cfg, model, max_tokens, sys_text, messages)

    extra = backend_cfg.get("extra_body")
    if extra and isinstance(extra, dict):
        body.update(extra)

    if stream or backend_cfg.get("force_stream_param"):
        body["stream"] = bool(stream)

    if tools:
        body["tools"] = tools

    return json.dumps(body).encode()
