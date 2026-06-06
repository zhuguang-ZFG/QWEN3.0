"""OpenCode coding path for routing_engine.

Extracted from routing_engine.py to keep the main route() skeleton concise.
Handles: opencode_tool_aware, reasoning_bridge, tool_splitter, code_orchestrator.
"""

from __future__ import annotations

import logging
import time

import health_tracker
from routing_engine_response import with_injection_meta
from routing_engine_types import RouteResult

_log = logging.getLogger(__name__)


def try_code_orchestration(
    messages: list[dict],
    query: str,
    call_fn,
    max_tokens: int,
    *,
    ide_source: str = "",
    system_prompt: str = "",
    tools: list[dict] | None = None,
    headers: dict | None = None,
    needs_tools: bool = False,
    scenario: str = "coding",
    t0: float,
    retrieval_text: str = "",
    injected_ids: list[str],
) -> RouteResult | None:
    """Attempt the OpenCode coding orchestration path.

    Returns a RouteResult on success, or None to fall through to the
    standard routing path.
    """
    try:
        # ── Inject OpenCode tool-aware prompts before code orchestration ──
        try:
            from opencode_tool_aware import inject_opencode_prompt

            messages = inject_opencode_prompt(
                messages, backend="", system_prompt=system_prompt,
                tools=tools, headers=headers or {},
            )
        except (ImportError, Exception) as _e:
            _log.debug("opencode_tool_aware failed: %s", _e)

        # ── Inject reasoning bridge (thinking reminder + provider prompt) ──
        _inject_reasoning_bridge(
            messages, needs_tools=needs_tools,
            ide_source=ide_source, tools=tools,
        )

        # ── Run code orchestrator ──
        import code_orchestrator

        orch_result = code_orchestrator.handle(
            query, messages, call_fn, max_tokens,
            ide_source=ide_source,
        )
        if orch_result.get("answer"):
            ms = int((time.time() - t0) * 1000)
            return with_injection_meta(RouteResult(
                backend=orch_result["backend"],
                answer=orch_result["answer"],
                request_type=f"code_{orch_result['tier']}",
                ms=ms, scenario=scenario,
                retrieval_context=retrieval_text,
                skills_injected=injected_ids,
            ), orch_result["backend"])
    except Exception as e:
        _log.warning("[ORCH] code_orchestrator failed: %s: %s", type(e).__name__, e)

    return None


def _inject_reasoning_bridge(
    messages: list[dict],
    *,
    needs_tools: bool = False,
    ide_source: str = "",
    tools: list[dict] | None = None,
) -> None:
    """Inject reasoning bridge hints (thinking reminder + provider prompt + tool splitter)."""
    try:
        from opencode_reasoning_bridge import (
            inject_thinking_reminder,
            select_provider_system_prompt,
        )

        # Estimate backend for coding path
        est_backend = ""
        try:
            from routing_selector import select as _rselect

            hmap = health_tracker.get_health_map()
            candidates = _rselect(
                "ide", hmap, scenario="coding",
                needs_tools=needs_tools, ide_source=ide_source,
            )
            est_backend = candidates[0] if candidates else ""
        except Exception:
            _log.debug("backend estimation failed", exc_info=True)

        if not est_backend:
            return

        messages_ref = messages  # mutable list, modified in-place
        inject_thinking_reminder(messages_ref, est_backend)

        provider_hint = select_provider_system_prompt(est_backend)
        if provider_hint:
            _append_to_system(messages_ref, provider_hint)

        # Sequential tool hint for weak backends
        try:
            from opencode_tool_splitter import (
                build_sequential_tool_prompt,
                should_inject_sequential_hint,
            )

            if should_inject_sequential_hint(est_backend):
                seq_hint = build_sequential_tool_prompt(tools)
                if seq_hint:
                    _append_to_system(messages_ref, seq_hint)
        except (ImportError, Exception) as _e2:
            _log.debug("tool_splitter hint failed: %s", _e2)
    except (ImportError, Exception) as _e:
        _log.debug("reasoning_bridge failed: %s", _e)


def _append_to_system(messages: list[dict], text: str) -> None:
    """Append *text* to the first system message, or insert one if absent."""
    sys_idx = next(
        (i for i, m in enumerate(messages) if m.get("role") == "system"),
        -1,
    )
    if sys_idx >= 0:
        old = messages[sys_idx].get("content", "")
        if isinstance(old, str):
            messages[sys_idx] = {
                **messages[sys_idx],
                "content": old.rstrip() + "\n" + text,
            }
    else:
        messages.insert(0, {"role": "system", "content": text})


# Backward-compat alias
inject_coding_opencode_prompts = try_code_orchestration
