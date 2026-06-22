"""Chat request preflight: guardrails, prompt context, budget (CQ-014 slice 10)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from chat_models import ChatRequest, extract_system_prompt
from device_mode import should_skip_context_pipeline
from prompt_engineering.device_intent_prompt import merge_device_intent_system_prompt
from response_builder import extract_query, messages_to_dicts
from server_context import build_prompt_context, messages_with_system_context

_log = logging.getLogger(__name__)


@dataclass
class ChatPreflightResult:
    request_messages: list[dict]
    prompt_context_messages: list[dict]
    system_prompt: str
    memory_recall_meta: dict
    memory_session_id: str | None


def run_input_guardrails(req: ChatRequest) -> None:
    if should_skip_context_pipeline():
        _log.debug("Skipping input guardrails in device mode")
        return

    from context_pipeline.guardrails import GuardrailSeverity, run_input_guardrails as _run

    raw_messages: list[dict] = [
        {"role": m.role, "content": m.content}
        if hasattr(m, "role")
        else {"role": m.get("role", ""), "content": m.get("content", "")}  # type: ignore[reportAssignmentType]
        for m in req.messages
    ]
    guard_result = _run(raw_messages)
    if not guard_result.passed and guard_result.severity == GuardrailSeverity.BLOCK:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=422,
            detail=f"Input blocked: {guard_result.violations}",
        )


def apply_token_budget(
    req: ChatRequest,
    request_messages: list[dict],
    system_prompt: str,
    ide_source: str,
) -> tuple[list[dict], list[dict]]:
    prompt_messages = messages_with_system_context(request_messages, system_prompt)

    if should_skip_context_pipeline():
        _log.debug("Skipping token budget check in device mode")
        return request_messages, prompt_messages

    from context_pipeline.token_budget import check_budget

    budget_status = check_budget(
        request_messages,
        system_prompt or "",
        "coding" if ide_source else "chat",
    )
    if not budget_status["within_budget"] and budget_status["action"] == "truncate_context":
        if len(req.messages) > 10:
            req.messages = req.messages[:3] + req.messages[-7:]
            request_messages = messages_to_dicts(req.messages)
            prompt_messages = messages_with_system_context(request_messages, system_prompt)
    return request_messages, prompt_messages


def adapt_identity_prompt(system_prompt: str, client_ip: str, request_messages: list[dict]):
    # adapt_system_prompt is not yet implemented in user_identity.adapter
    from user_identity.adapter import adapt_system_prompt  # type: ignore[reportAttributeAccessIssue,reportArgumentType]  # noqa: F401

    adapted = adapt_system_prompt(system_prompt or "", client_ip)
    if adapted != system_prompt:
        return adapted, messages_with_system_context(request_messages, adapted)
    return system_prompt, messages_with_system_context(request_messages, system_prompt)


def prepare_chat_preflight(
    req: ChatRequest,
    *,
    client_ip: str = "",
    ide_source: str = "",
    sys_prompt_preview: str = "",
    request_headers: dict | None = None,
    trace=None,
) -> ChatPreflightResult:
    try:
        run_input_guardrails(req)
    except ImportError:
        _log.warning("context_pipeline.guardrails not installed; skipping input guardrails")

    prompt_ctx = build_prompt_context(
        req,
        system_prompt=extract_system_prompt(req.messages) or sys_prompt_preview or "",
        request_headers=request_headers,
        client_ip=client_ip,
        ide_source=ide_source,
        trace=trace,
    )
    request_messages = prompt_ctx.request_messages
    prompt_context_messages = prompt_ctx.prompt_context_messages
    system_prompt = prompt_ctx.system_prompt

    query = extract_query(req.messages)
    system_prompt = merge_device_intent_system_prompt(
        query,
        system_prompt,
        ide_source=ide_source,
    )
    prompt_context_messages = messages_with_system_context(request_messages, system_prompt)

    try:
        request_messages, prompt_context_messages = apply_token_budget(req, request_messages, system_prompt, ide_source)
    except ImportError:
        _log.warning("token budget module not installed; skipping apply_token_budget")

    try:
        system_prompt, prompt_context_messages = adapt_identity_prompt(system_prompt, client_ip, request_messages)
    except ImportError:
        _log.warning("identity adapter not installed; skipping adapt_identity_prompt")

    return ChatPreflightResult(
        request_messages=request_messages,
        prompt_context_messages=prompt_context_messages,
        system_prompt=system_prompt,
        memory_recall_meta=prompt_ctx.memory_recall_meta,
        memory_session_id=prompt_ctx.memory_session_id,
    )
