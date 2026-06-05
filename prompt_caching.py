"""OpenCode prompt caching hints — cache_control injection for Anthropic-format backends.

Implements client-side caching hints for OpenCode requests that target backends
which accept Anthropic's `cache_control` content-block field (Anthropic API,
Longcat Anthropic proxy, and any OpenRouter model exposing Anthropic Messages
format). For all other formats (OpenAI Chat Completions, Google Generative AI,
plain HTTP) the function is a no-op — those backends cache automatically on
the server side or have no equivalent field.

Design notes
------------
- Anthropic allows up to 4 cache_control breakpoints per request. We place
  exactly two: one on the trailing system content block (caches the static
  system prompt + any injected skills) and one on the last content block of
  the final user turn (caches the long conversation tail).
- We always convert a bare-string `system` / `content` to a list-of-content-
  blocks in-place; this matches the documented Anthropic shape and is
  non-destructive for callers that already pass list form.
- We never raise: malformed bodies are passed through unchanged so that
  downstream HTTP transport can surface the real error. Returning early on
  shape mismatch is the safer fallback.
- The function mutates `body` in place for the common case and returns it
  unchanged to allow call-site chaining.
"""
from __future__ import annotations

from typing import Any

#: Anthropic ephemeral cache control type. The only valid value for typical
#: chat requests; "long" cache_control (1h) is reserved for fine-grained
#: batch workloads and is intentionally not exposed here.
_CACHE_CONTROL_BLOCK: dict[str, str] = {"type": "ephemeral"}


def _ensure_block_list(field: Any) -> list[dict[str, Any]] | None:
    """Return `field` as a list of content blocks, or None if unrecoverable.

    Accepts:
      * list[dict]  — returned as-is (a shallow copy is taken when mutating)
      * str          — wrapped in a single text block
      * anything else (None, int, …) → returns None (caller should no-op)
    """
    if isinstance(field, list):
        return field
    if isinstance(field, str):
        return [{"type": "text", "text": field}]
    return None


def _attach_cache_control(block: dict[str, Any]) -> None:
    """Stamp `cache_control` onto a single content block in place."""
    block["cache_control"] = dict(_CACHE_CONTROL_BLOCK)


def inject_cache_control(body: dict[str, Any], fmt: str) -> dict[str, Any]:
    """Add cache_control hints to `body` if `fmt == "anthropic"`.

    Parameters
    ----------
    body
        The outgoing chat-completions / messages body dict. Mutated in place
        when hints are added; returned unchanged in the no-op cases.
    fmt
        Wire format of the body. One of ``"anthropic"``, ``"openai"``,
        ``"google"`` or any other provider-specific string. Only
        ``"anthropic"`` receives hints; the rest are passed through.

    Returns
    -------
    The same ``body`` dict, mutated or unchanged. Returning it is purely
    ergonomic for call sites that prefer a fluent style.
    """
    if fmt != "anthropic" or not isinstance(body, dict):
        return body

    # 1) Hint the trailing system block so the static prompt + injected
    #    skills are cached. This is the highest-leverage breakpoint
    #    because the system prompt is identical across turns.
    system = body.get("system")
    system_blocks = _ensure_block_list(system)
    if system_blocks:
        body["system"] = system_blocks
        if system_blocks and isinstance(system_blocks[-1], dict):
            _attach_cache_control(system_blocks[-1])

    # 2) Hint the last content block of the final user turn. This caches
    #    the long conversation tail, which is the second-biggest stable
    #    prefix after the system prompt.
    messages = body.get("messages")
    if not isinstance(messages, list) or not messages:
        return body

    for msg in reversed(messages):
        if not isinstance(msg, dict):
            continue
        if msg.get("role") != "user":
            continue
        content = msg.get("content")
        blocks = _ensure_block_list(content)
        if not blocks:
            return body
        msg["content"] = blocks
        if blocks and isinstance(blocks[-1], dict):
            _attach_cache_control(blocks[-1])
        break

    return body
