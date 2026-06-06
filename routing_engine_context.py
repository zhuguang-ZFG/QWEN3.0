"""Context injection pipeline for routing_engine.

Extracted from routing_engine.py to keep the main route() skeleton concise.
Handles: trace, retrieval, enrich, web search, code context, complexity, skills.
"""

from __future__ import annotations

import logging

from routing_engine_skills import get_injected_ids as _get_injected_ids
from routing_engine_skills import inject_skills

_log = logging.getLogger(__name__)


def inject_all_context(
    messages: list[dict],
    *,
    query: str,
    scenario: str,
    req_type: str,
    ide_source: str = "",
    system_prompt: str = "",
    client_ip: str = "",
    user_agent: str = "",
) -> tuple[list[dict], str, str, list[str]]:
    """Run the full context injection pipeline.

    Returns (messages, retrieval_text, recalled_backend, injected_ids).
    """
    # ── Begin injection trace ──
    try:
        from context_injection_trace import begin_trace

        begin_trace(scenario=scenario, request_type=req_type)
    except ImportError:
        _log.debug("context_injection_trace not available")

    # ── Skill store recall ──
    recalled_backend = ""
    try:
        from context_pipeline.skill_store import get_skill_store

        recalled = get_skill_store().recall(messages, scenario)
        if recalled:
            recalled_backend = recalled.backend
    except ImportError as e:
        _log.debug("skill_store not available: %s", e)

    # ── Retrieval context ──
    from context_pipeline.retrieval_injection import inject_retrieval_context

    messages, retrieval_text = inject_retrieval_context(messages)
    try:
        from context_injection_trace import record_retrieval

        record_retrieval(retrieval_text)
    except ImportError:
        pass

    # ── Enriched context: date/time + location + device ──
    try:
        from context_pipeline.enrich_context import inject_enriched_context

        messages = inject_enriched_context(
            messages, client_ip=client_ip, user_agent=user_agent,
        )
    except Exception as e:
        _log.debug("enrich_context injection failed: %s", e)

    # ── Web search context: detect + search + inject ──
    web_search_text = ""
    try:
        from context_pipeline.web_search_context import inject_web_search_context

        messages, web_search_text = inject_web_search_context(query, messages)
        if web_search_text:
            retrieval_text = (retrieval_text + "\n" + web_search_text).strip()
            try:
                from context_injection_trace import record_web_search

                record_web_search(web_search_text)
            except ImportError:
                pass
    except Exception as e:
        _log.debug("web_search_context injection failed: %s", e)

    # ── Code context injection ──
    if scenario == "coding":
        try:
            from context_pipeline.code_context_injection import scan_and_build_context

            code_context_text = scan_and_build_context(query, messages)
            if code_context_text:
                code_ctx_msg = {"role": "system", "content": code_context_text}
                if messages and messages[0].get("role") == "system":
                    messages.insert(1, code_ctx_msg)
                else:
                    messages.insert(0, code_ctx_msg)
                try:
                    from context_injection_trace import record_code_context

                    record_code_context(code_context_text)
                except ImportError:
                    pass
        except Exception as e:
            _log.debug("code_context_injection failed: %s", e)

    # ── Complexity assessment ──
    try:
        from context_pipeline.complexity import assess_complexity

        raw_msgs = [
            {"role": m.get("role", ""), "content": m.get("content", "")}
            if isinstance(m, dict)
            else {"role": getattr(m, "role", ""), "content": getattr(m, "content", "")}
            for m in messages
        ]
        assess_complexity(raw_msgs, ide=ide_source)
    except ImportError as e:
        _log.debug("complexity assessment not available: %s", e)

    # ── Skills injection (early pass, backend unknown) ──
    msg_count_before = len(messages)
    try:
        messages = inject_skills(
            messages, backend="",
            ide_source=ide_source, system_prompt=system_prompt,
        )
    except Exception as _e:
        _log.warning("[SKILLS] early injection failed: %s: %s", type(_e).__name__, _e)
    injected_ids = _get_injected_ids(list(messages[:msg_count_before]), messages)
    try:
        from context_injection_trace import record_skills

        record_skills(injected_ids)
    except ImportError:
        pass

    return messages, retrieval_text, recalled_backend, injected_ids


# Backward-compat alias
prepare_route_context = inject_all_context
