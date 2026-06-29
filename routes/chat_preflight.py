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
        "chat",
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


def _build_prompt_context_from_request(
    req: ChatRequest,
    *,
    client_ip: str,
    ide_source: str,
    sys_prompt_preview: str,
    request_headers: dict | None,
    trace,
):
    """Build prompt context and apply device intent merge.

    AUDIT-3-P4：客户端 system 消息仅在非设备意图场景保留；当 LiMa 设备意图层激活时，
    LiMa 系统提示完全覆盖客户端 system，避免攻击者通过 system 消息注入指令。
    """
    client_system = extract_system_prompt(req.messages) or sys_prompt_preview or ""
    # 先让记忆召回基于空 system_prompt 工作，避免把客户端 system 作为“上下文”拼入 LiMa 层。
    prompt_ctx = build_prompt_context(
        req,
        system_prompt="",
        request_headers=request_headers,
        client_ip=client_ip,
        ide_source=ide_source,
        trace=trace,
    )
    request_messages = prompt_ctx.request_messages
    memory_system = prompt_ctx.system_prompt
    merged_system = merge_device_intent_system_prompt(
        extract_query(req.messages),
        memory_system,
        ide_source=ide_source,
    )
    # 无设备意图时恢复客户端 system（OpenAI 兼容）；有设备意图时 LiMa 层已覆盖。
    if merged_system == memory_system:
        system_prompt = (client_system + "\n\n" + memory_system).strip()
    else:
        system_prompt = merged_system
    prompt_context_messages = messages_with_system_context(request_messages, system_prompt)
    return request_messages, prompt_context_messages, system_prompt, prompt_ctx


def prepare_chat_preflight(
    req: ChatRequest,
    *,
    client_ip: str = "",
    ide_source: str = "",
    sys_prompt_preview: str = "",
    request_headers: dict | None = None,
    trace=None,
) -> ChatPreflightResult:
    """Run guardrails, build context, and apply budget/identity adaptations."""
    try:
        run_input_guardrails(req)
    except ImportError:
        _log.warning("context_pipeline.guardrails not installed; skipping input guardrails")

    request_messages, prompt_context_messages, system_prompt, prompt_ctx = _build_prompt_context_from_request(
        req,
        client_ip=client_ip,
        ide_source=ide_source,
        sys_prompt_preview=sys_prompt_preview,
        request_headers=request_headers,
        trace=trace,
    )

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
