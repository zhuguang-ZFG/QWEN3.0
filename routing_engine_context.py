"""Context preparation helpers for routing_engine."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class PreparedRouteContext:
    messages: list[dict]
    retrieval_text: str = ""
    recalled_backend: str = ""
    injected_ids: list[str] = field(default_factory=list)


def begin_injection_trace(*, scenario: str, request_type: str) -> None:
    try:
        from context_injection_trace import begin_trace

        begin_trace(scenario=scenario, request_type=request_type)
    except ImportError:
        logging.debug("routing_engine_context: context_injection_trace not available")


def prepare_route_context(
    query: str,
    messages: list[dict],
    *,
    scenario: str,
    request_type: str,
    ide_source: str,
    system_prompt: str,
    client_ip: str,
    user_agent: str,
    retrieval_injector: Callable[[list[dict]], tuple[list[dict], str]],
    skills_injector: Callable[..., list[dict]],
    injected_id_getter: Callable[[list[dict], list[dict]], list[str]],
) -> PreparedRouteContext:
    begin_injection_trace(scenario=scenario, request_type=request_type)
    recalled_backend = _recall_backend(messages, scenario)
    messages, retrieval_text = retrieval_injector(messages)
    _record_retrieval(retrieval_text)
    messages = _inject_enriched_context(messages, client_ip=client_ip, user_agent=user_agent)
    messages, retrieval_text = _inject_web_search(query, messages, retrieval_text)
    messages = _inject_code_context(query, messages, scenario)
    _assess_complexity(messages, ide_source=ide_source)

    count_before = len(messages)
    try:
        messages = skills_injector(messages, backend="", ide_source=ide_source, system_prompt=system_prompt)
    except Exception as exc:
        logging.warning("[SKILLS] early injection failed: %s: %s", type(exc).__name__, exc)

    injected_ids = injected_id_getter(list(messages[:count_before]), messages)
    _record_skills(injected_ids)
    return PreparedRouteContext(
        messages=messages,
        retrieval_text=retrieval_text,
        recalled_backend=recalled_backend,
        injected_ids=injected_ids,
    )


def _recall_backend(messages: list[dict], scenario: str) -> str:
    try:
        from context_pipeline.skill_store import get_skill_store

        recalled = get_skill_store().recall(messages, scenario)
        return recalled.backend if recalled else ""
    except ImportError as exc:
        logging.debug("routing_engine: skill_store not available: %s", exc)
    return ""


def _record_retrieval(retrieval_text: str) -> None:
    try:
        from context_injection_trace import record_retrieval

        record_retrieval(retrieval_text)
    except ImportError:
        logging.debug("routing_engine_context: context_injection_trace not available")


def _inject_enriched_context(messages: list[dict], *, client_ip: str, user_agent: str) -> list[dict]:
    try:
        from context_pipeline.enrich_context import inject_enriched_context

        return inject_enriched_context(messages, client_ip=client_ip, user_agent=user_agent)
    except Exception as exc:
        logging.debug("routing_engine: enrich_context injection failed: %s", exc)
    return messages


def _inject_web_search(query: str, messages: list[dict], retrieval_text: str) -> tuple[list[dict], str]:
    try:
        from context_pipeline.web_search_context import inject_web_search_context

        messages, web_search_text = inject_web_search_context(query, messages)
        if web_search_text:
            retrieval_text = (retrieval_text + "\n" + web_search_text).strip()
            try:
                from context_injection_trace import record_web_search

                record_web_search(web_search_text)
            except ImportError:
                logging.debug("routing_engine_context: context_injection_trace not available")
    except Exception as exc:
        logging.debug("routing_engine: web_search_context injection failed: %s", exc)
    return messages, retrieval_text


def _inject_code_context(query: str, messages: list[dict], scenario: str) -> list[dict]:
    if scenario != "coding":
        return messages
    try:
        from context_pipeline.code_context_injection import scan_and_build_context

        code_context_text = scan_and_build_context(query, messages)
        if not code_context_text:
            return messages
        code_context_message = {"role": "system", "content": code_context_text}
        if messages and messages[0].get("role") == "system":
            messages.insert(1, code_context_message)
        else:
            messages.insert(0, code_context_message)
        try:
            from context_injection_trace import record_code_context

            record_code_context(code_context_text)
        except ImportError:
            logging.debug("routing_engine_context: context_injection_trace not available")
    except Exception as exc:
        logging.debug("code_context_injection failed: %s", exc)
    return messages


def _assess_complexity(messages: list[dict], *, ide_source: str) -> None:
    try:
        from context_pipeline.complexity import assess_complexity

        raw_messages = [
            {"role": m.get("role", ""), "content": m.get("content", "")}
            if isinstance(m, dict)
            else {"role": getattr(m, "role", ""), "content": getattr(m, "content", "")}
            for m in messages
        ]
        assess_complexity(raw_messages, ide=ide_source)
    except ImportError as exc:
        logging.debug("routing_engine: complexity assessment not available: %s", exc)


def _record_skills(injected_ids: list[str]) -> None:
    try:
        from context_injection_trace import record_skills

        record_skills(injected_ids)
    except ImportError:
        logging.debug("routing_engine_context: context_injection_trace not available")
