"""V3 路由适配器：将 routing_engine 的结果适配为 server.py 兼容格式。

从 server.py 提取，保持接口不变，去掉前导下划线。
"""

import logging
from collections.abc import AsyncIterator

import routing_engine
from routing_engine import classify_scenario
import http_caller


def v3_route(
    query, messages, system_prompt="", ide="", max_tokens=4096, needs_tools=False, tools=None, prefer=None, **_kw
):
    """V3 路由适配器：返回与 smart_router.route() 兼容的 dict。"""

    def _call_fn(backend, msgs, mt, tools=None):
        return http_caller.call_api(backend, msgs, mt, system_prompt=system_prompt, ide=ide, tools=tools)

    result = routing_engine.route(
        query,
        messages,
        fmt="openai",
        ide_source=ide,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
        call_fn=_call_fn,
        needs_tools=needs_tools,
        tools=tools,
        preferred_backend=prefer or "",
    )
    return {
        "answer": result.answer,
        "backend": result.backend,
        "total_ms": result.ms,
        "fallback_used": result.fallback_used,
    }


_FALLBACK_BACKEND = "longcat_chat"


def _normalize_ide_source(ide: str) -> str:
    return ide if ide and ide not in ("unknown", "") else ""


def _pick_for_stream(
    query: str,
    messages: list,
    *,
    system_prompt: str = "",
    ide: str = "",
    preferred_backend: str = "",
):
    """流式 speculative 选路：与 v3_select 共享 pick_backend 入参。"""
    msgs = messages if messages else [{"role": "user", "content": query}]
    return routing_engine.pick_backend(
        query,
        msgs,
        ide_source=_normalize_ide_source(ide),
        system_prompt=system_prompt or "",
        preferred_backend=preferred_backend or "",
    )


def v3_predict(query, messages, system_prompt="", ide="", preferred_backend=""):
    """V3 快速预测：委托 routing_engine.pick_backend（与 v3_select 共享上下文）。"""
    try:
        picked = _pick_for_stream(
            query,
            messages,
            system_prompt=system_prompt,
            ide=ide,
            preferred_backend=preferred_backend,
        )
        return picked.backend
    except Exception as e:
        logging.warning(f"[V3_PREDICT] pick_backend failed: {type(e).__name__}: {e}")
        return _FALLBACK_BACKEND


def v3_select(query, system_prompt, ide, messages, preferred_backend=""):
    """V3 完整路由选择：委托 routing_engine.pick_backend。"""
    try:
        picked = _pick_for_stream(
            query,
            messages,
            system_prompt=system_prompt,
            ide=ide,
            preferred_backend=preferred_backend,
        )
        return (picked.backend, picked.messages)
    except Exception as e:
        logging.warning(f"[V3_SELECT] pick_backend failed: {type(e).__name__}: {e}")
        return (_FALLBACK_BACKEND, messages)


# 非真流式后端（代理/逆向），强制走非流式保证身份清洗完整
FAKE_STREAM_BACKENDS = {"deepseek_free"}


def v3_call_stream(backend, messages, max_tokens, ide):
    """V3 流式调用适配器。注入上下文增强 + 非真流式后端强制走非流式。"""
    sys_prompt = ""
    try:
        from lima_context import build_context_digest

        query = ""
        for m in reversed(messages):
            if m.get("role") == "user" and isinstance(m.get("content"), str):
                query = m["content"]
                break
        if query:
            is_ide = bool(ide and ide not in ("unknown", ""))
            scenario = classify_scenario(
                messages,
                query=query,
                ide_source=ide if is_ide else "",
                request_type="ide" if is_ide else "chat",
            )
            if scenario == "coding":
                digest = build_context_digest(query, messages, ide_source=ide)
                if digest:
                    sys_prompt = digest
                # Layer think/plan on top of context (not instead of)
                try:
                    from think_plan_context import enhance_coding_prompt, needs_plan

                    if needs_plan(query):
                        tpc = enhance_coding_prompt(query, messages)
                        if tpc.get("system_prompt"):
                            sys_prompt = tpc["system_prompt"] + "\n\n" + sys_prompt
                        if tpc.get("context_files"):
                            ctx_summary = "\nRelated files: " + ", ".join(tpc["context_files"][:5])
                            if messages and messages[-1].get("role") == "user":
                                messages[-1] = {
                                    **messages[-1],
                                    "content": str(messages[-1].get("content", "")) + ctx_summary,
                                }
                except ImportError:
                    logging.getLogger(__name__).warning(
                        "think_plan_context not available; coding prompt enhancement disabled"
                    )
            else:
                sys_prompt = "Answer the question directly in plain text. Do not generate code, functions, or programming examples unless the user explicitly asks for code."
    except Exception as e:
        logging.warning(f"[V3_CALL_STREAM] context enhance failed: {type(e).__name__}: {e}")

    if backend in FAKE_STREAM_BACKENDS:
        result = http_caller.call_api(backend, messages, max_tokens, system_prompt=sys_prompt, ide=ide)
        return fake_stream(result)
    return http_caller.call_api_stream(backend, messages, max_tokens, system_prompt=sys_prompt, ide=ide)


def v3_call_api(backend, messages, max_tokens, ide):
    """V3 非流式调用适配器。含场景检测 + 反向约束。"""
    sys_prompt = ""
    try:

        query = next(
            (m["content"] for m in reversed(messages) if m.get("role") == "user" and isinstance(m.get("content"), str)),
            "",
        )
        if query:
            is_ide = bool(ide and ide not in ("unknown", ""))
            scenario = classify_scenario(
                messages,
                query=query,
                ide_source=ide if is_ide else "",
                request_type="ide" if is_ide else "chat",
            )
            if scenario == "coding":
                from lima_context import build_context_digest

                digest = build_context_digest(query, messages, ide_source=ide)
                if digest:
                    sys_prompt = digest
            else:
                no_code = "Answer the question directly in plain text. Do not generate code, functions, or programming examples unless the user explicitly asks for code."
                messages = [{"role": "system", "content": no_code}] + list(messages)
    except Exception as e:
        logging.warning(f"[V3_CALL_API] context enhance failed: {type(e).__name__}: {e}")
    return http_caller.call_api(backend, messages, max_tokens, system_prompt=sys_prompt, ide=ide)


def fake_stream(text: str, chunk_size: int = 30):
    """将完整文本拆为 chunk 模拟流式输出。已清洗的文本直接拆。"""
    for i in range(0, len(text), chunk_size):
        yield text[i : i + chunk_size]


# ── Async adapters (M2-S2) ─────────────────────────────────────────────────


async def v3_call_stream_async(backend, messages, max_tokens, ide) -> AsyncIterator[str]:
    """Async streaming adapter. Falls back to non-stream for fake-stream backends."""
    sys_prompt = _build_async_stream_prompt(messages, ide)

    if backend in FAKE_STREAM_BACKENDS:
        result = await http_caller.call_api_async(backend, messages, max_tokens, system_prompt=sys_prompt, ide=ide)
        for chunk in fake_stream(result):
            yield chunk
        return
    async for chunk in http_caller.call_api_stream_async(
        backend, messages, max_tokens, system_prompt=sys_prompt, ide=ide
    ):
        yield chunk


def _build_async_stream_prompt(messages: list, ide: str) -> str:
    """Build system prompt for async stream: coding context or plain-text constraint."""
    sys_prompt = ""
    try:
        from lima_context import build_context_digest

        query = next(
            (m["content"] for m in reversed(messages) if m.get("role") == "user" and isinstance(m.get("content"), str)),
            "",
        )
        if query:
            is_ide = bool(ide and ide not in ("unknown", ""))
            scenario = classify_scenario(
                messages, query=query, ide_source=ide if is_ide else "", request_type="ide" if is_ide else "chat",
            )
            if scenario == "coding":
                digest = build_context_digest(query, messages, ide_source=ide)
                if digest:
                    sys_prompt = digest
                try:
                    from think_plan_context import enhance_coding_prompt, needs_plan

                    if needs_plan(query):
                        tpc = enhance_coding_prompt(query, messages)
                        if tpc.get("system_prompt"):
                            sys_prompt = tpc["system_prompt"] + "\n\n" + sys_prompt
                        if tpc.get("context_files"):
                            ctx_summary = "\nRelated files: " + ", ".join(tpc["context_files"][:5])
                            if messages and messages[-1].get("role") == "user":
                                messages[-1] = {**messages[-1], "content": str(messages[-1].get("content", "")) + ctx_summary}
                except ImportError:
                    logging.getLogger(__name__).info("think_plan_context not installed; skipping plan enhancement")
            else:
                sys_prompt = "Answer the question directly in plain text. Do not generate code, functions, or programming examples unless the user explicitly asks for code."
    except Exception as e:
        logging.warning(f"[V3_CALL_STREAM_ASYNC] context enhance: {type(e).__name__}: {e}")
    return sys_prompt


async def v3_call_api_async(backend, messages, max_tokens, ide):
    """Async non-streaming adapter."""
    sys_prompt = ""
    try:

        query = next(
            (m["content"] for m in reversed(messages) if m.get("role") == "user" and isinstance(m.get("content"), str)),
            "",
        )
        if query:
            is_ide = bool(ide and ide not in ("unknown", ""))
            scenario = classify_scenario(
                messages,
                query=query,
                ide_source=ide if is_ide else "",
                request_type="ide" if is_ide else "chat",
            )
            if scenario == "coding":
                from lima_context import build_context_digest

                digest = build_context_digest(query, messages, ide_source=ide)
                if digest:
                    sys_prompt = digest
            else:
                no_code = "Answer the question directly in plain text. Do not generate code, functions, or programming examples unless the user explicitly asks for code."
                messages = [{"role": "system", "content": no_code}] + list(messages)
    except Exception as e:
        logging.warning(f"[V3_CALL_API_ASYNC] context enhance: {type(e).__name__}: {e}")
    return await http_caller.call_api_async(backend, messages, max_tokens, system_prompt=sys_prompt, ide=ide)
