"""V3 路由适配器：将 routing_engine 的结果适配为 server.py 兼容格式。

从 server.py 提取，保持接口不变，去掉前导下划线。
"""
import logging
from collections.abc import AsyncIterator

import routing_engine
import http_caller
import health_tracker


def v3_route(query, messages, system_prompt="", ide="", max_tokens=4096,
             needs_tools=False, tools=None, client_ip="", user_agent="",
             model="", **_kw):
    """V3 路由适配器：返回与 smart_router.route() 兼容的 dict。"""
    def _call_fn(backend, msgs, mt, tools=None):
        return http_caller.call_api(backend, msgs, mt,
                                    system_prompt=system_prompt, ide=ide,
                                    tools=tools)
    result = routing_engine.route(
        query, messages, fmt="openai", ide_source=ide,
        system_prompt=system_prompt, max_tokens=max_tokens,
        call_fn=_call_fn, needs_tools=needs_tools, tools=tools,
        client_ip=client_ip, user_agent=user_agent, model=model)
    return {"answer": result.answer, "backend": result.backend,
            "total_ms": result.ms, "fallback_used": result.fallback_used}


def v3_predict(query):
    """V3 快速预测：根据场景选择后端池。"""
    hmap = health_tracker.get_health_map()
    try:
        from routing_engine import classify_scenario
        scenario = classify_scenario(query, [], request_type="")
        if scenario == "coding":
            # scnet_ds_flash has strong coding capability (non-streaming verified)
            stream_stable = ["longcat_chat", "scnet_ds_flash", "scnet_qwen235b",
                             "scnet_qwen30b", "groq_gptoss", "github_gpt4o",
                             "mistral_small", "cerebras_gptoss"]
            for b in stream_stable:
                if not health_tracker.is_cooled_down(b):
                    return b
            import code_orchestrator
            pool = code_orchestrator.backend_reputation.sort_by_reputation(
                code_orchestrator.POOLS["coder"])
            if pool:
                return pool[0]
        else:
            chat_only = ["longcat_chat", "zhipu_flash", "cf_llama70b",
                         "groq_llama70b", "longcat_lite"]
            for b in chat_only:
                if not health_tracker.is_cooled_down(b):
                    return b
            return "longcat_chat"
    except Exception as e:
        logging.warning(f"[V3_SELECT] classify/context failed: {type(e).__name__}: {e}")
    backends = routing_engine.select("chat", hmap, scenario="chat")
    return backends[0] if backends else "longcat_chat"


def v3_select(query, system_prompt, ide, messages):
    """V3 完整路由选择：根据场景选后端。"""
    hmap = health_tracker.get_health_map()
    is_ide = bool(ide and ide not in ("unknown", ""))

    # Retrieval injection for streaming path
    try:
        messages, _ = routing_engine.inject_retrieval_context(messages)
    except Exception as e:
        logging.warning(f"[V3_SELECT] retrieval injection failed: {type(e).__name__}: {e}")

    try:
        from routing_engine import classify_scenario
        scenario = classify_scenario(query, messages,
                                     ide_source=ide if is_ide else "",
                                     request_type="ide" if is_ide else "chat")
        if scenario == "coding":
            stream_stable = ["longcat_chat", "scnet_qwen235b", "scnet_qwen30b",
                             "groq_gptoss", "cerebras_gptoss", "github_gpt4o",
                             "mistral_small"]
            for b in stream_stable:
                if not health_tracker.is_cooled_down(b):
                    return (b, messages)
            import code_orchestrator
            pool = code_orchestrator.backend_reputation.sort_by_reputation(
                code_orchestrator.POOLS["coder"])
            if pool:
                return (pool[0], messages)
        else:
            chat_only = ["longcat_chat", "zhipu_flash", "cf_llama70b",
                         "groq_llama70b", "longcat_lite", "longcat_chat"]
            for b in chat_only:
                if not health_tracker.is_cooled_down(b):
                    return (b, messages)
            return ("groq_llama70b", messages)
    except Exception as e:
        logging.warning(f"[V3_STREAM] classify/context failed: {type(e).__name__}: {e}")
    backends = routing_engine.select("chat", hmap, scenario="chat")
    return (backends[0] if backends else "longcat_chat", messages)


# M6: deepseek_free deleted. No fake-stream backends remain.
FAKE_STREAM_BACKENDS: set[str] = set()


def v3_call_stream(backend, messages, max_tokens, ide):
    """V3 流式调用适配器。注入上下文增强 + 非真流式后端强制走非流式。"""
    sys_prompt = ""
    try:
        import code_orchestrator
        from routing_engine import classify_scenario
        query = ""
        for m in reversed(messages):
            if m.get("role") == "user" and isinstance(m.get("content"), str):
                query = m["content"]
                break
        if query:
            is_ide = bool(ide and ide not in ("unknown", ""))
            scenario = classify_scenario(query, messages,
                                         ide_source=ide if is_ide else "",
                                         request_type="ide" if is_ide else "chat")
            if scenario == "coding":
                ctx = code_orchestrator.enhance_context(query, messages, scenario)
                sys_prompt = ctx.get("system_prompt", "")
                messages = ctx.get("enhanced_messages", messages)
                # Layer think/plan on top of orchestrator (not instead of)
                try:
                    from think_plan_context import enhance_coding_prompt, needs_plan
                    if needs_plan(query):
                        tpc = enhance_coding_prompt(query, messages)
                        if tpc.get("system_prompt"):
                            sys_prompt = tpc["system_prompt"] + "\n\n" + sys_prompt
                        if tpc.get("context_files"):
                            ctx_summary = "\nRelated files: " + ", ".join(
                                tpc["context_files"][:5])
                            if messages and messages[-1].get("role") == "user":
                                messages[-1] = {
                                    **messages[-1],
                                    "content": str(messages[-1].get("content", ""))
                                    + ctx_summary,
                                }
                except ImportError:
                    pass
            else:
                sys_prompt = "Answer the question directly in plain text. Do not generate code, functions, or programming examples unless the user explicitly asks for code."
    except Exception as e:
        logging.warning(f"[V3_CALL_STREAM] context enhance failed: {type(e).__name__}: {e}")

    if backend in FAKE_STREAM_BACKENDS:
        result = http_caller.call_api(
            backend, messages, max_tokens, system_prompt=sys_prompt, ide=ide)
        return fake_stream(result)
    return http_caller.call_api_stream(
        backend, messages, max_tokens, system_prompt=sys_prompt, ide=ide)


def v3_call_api(backend, messages, max_tokens, ide):
    """V3 非流式调用适配器。含场景检测 + 反向约束。"""
    sys_prompt = ""
    try:
        from routing_engine import classify_scenario
        query = next((m["content"] for m in reversed(messages)
                      if m.get("role") == "user" and isinstance(m.get("content"), str)), "")
        if query:
            is_ide = bool(ide and ide not in ("unknown", ""))
            scenario = classify_scenario(query, messages,
                                         ide_source=ide if is_ide else "",
                                         request_type="ide" if is_ide else "chat")
            if scenario == "coding":
                import code_orchestrator
                ctx = code_orchestrator.enhance_context(query, messages, scenario)
                sys_prompt = ctx.get("system_prompt", "")
            else:
                no_code = "Answer the question directly in plain text. Do not generate code, functions, or programming examples unless the user explicitly asks for code."
                messages = [{"role": "system", "content": no_code}] + list(messages)
    except Exception as e:
        logging.warning(f"[V3_CALL_API] context enhance failed: {type(e).__name__}: {e}")
    return http_caller.call_api(
        backend, messages, max_tokens, system_prompt=sys_prompt, ide=ide)


def fake_stream(text: str, chunk_size: int = 30):
    """将完整文本拆为 chunk 模拟流式输出。已清洗的文本直接拆。"""
    for i in range(0, len(text), chunk_size):
        yield text[i:i+chunk_size]


# ── Async adapters (M2-S2) ─────────────────────────────────────────────────

async def v3_call_stream_async(backend, messages, max_tokens, ide) -> AsyncIterator[str]:
    """Async streaming adapter. Falls back to non-stream for fake-stream backends."""
    sys_prompt = ""
    try:
        import code_orchestrator
        from routing_engine import classify_scenario
        query = ""
        for m in reversed(messages):
            if m.get("role") == "user" and isinstance(m.get("content"), str):
                query = m["content"]
                break
        if query:
            is_ide = bool(ide and ide not in ("unknown", ""))
            scenario = classify_scenario(query, messages,
                                         ide_source=ide if is_ide else "",
                                         request_type="ide" if is_ide else "chat")
            if scenario == "coding":
                ctx = code_orchestrator.enhance_context(query, messages, scenario)
                sys_prompt = ctx.get("system_prompt", "")
                messages = ctx.get("enhanced_messages", messages)
                # Layer think/plan on top of orchestrator (not instead of)
                try:
                    from think_plan_context import enhance_coding_prompt, needs_plan
                    if needs_plan(query):
                        tpc = enhance_coding_prompt(query, messages)
                        if tpc.get("system_prompt"):
                            sys_prompt = tpc["system_prompt"] + "\n\n" + sys_prompt
                        if tpc.get("context_files"):
                            ctx_summary = "\nRelated files: " + ", ".join(
                                tpc["context_files"][:5])
                            if messages and messages[-1].get("role") == "user":
                                messages[-1] = {
                                    **messages[-1],
                                    "content": str(messages[-1].get("content", ""))
                                    + ctx_summary,
                                }
                except ImportError:
                    pass
            else:
                sys_prompt = "Answer the question directly in plain text. Do not generate code, functions, or programming examples unless the user explicitly asks for code."
    except Exception as e:
        logging.warning(f"[V3_CALL_STREAM_ASYNC] context enhance: {type(e).__name__}: {e}")

    if backend in FAKE_STREAM_BACKENDS:
        result = await http_caller.call_api_async(
            backend, messages, max_tokens, system_prompt=sys_prompt, ide=ide)
        for chunk in fake_stream(result):
            yield chunk
        return
    async for chunk in http_caller.call_api_stream_async(
        backend, messages, max_tokens, system_prompt=sys_prompt, ide=ide):
        yield chunk


async def v3_call_api_async(backend, messages, max_tokens, ide):
    """Async non-streaming adapter."""
    sys_prompt = ""
    try:
        from routing_engine import classify_scenario
        query = next((m["content"] for m in reversed(messages)
                      if m.get("role") == "user" and isinstance(m.get("content"), str)), "")
        if query:
            is_ide = bool(ide and ide not in ("unknown", ""))
            scenario = classify_scenario(query, messages,
                                         ide_source=ide if is_ide else "",
                                         request_type="ide" if is_ide else "chat")
            if scenario == "coding":
                import code_orchestrator
                ctx = code_orchestrator.enhance_context(query, messages, scenario)
                sys_prompt = ctx.get("system_prompt", "")
            else:
                no_code = "Answer the question directly in plain text. Do not generate code, functions, or programming examples unless the user explicitly asks for code."
                messages = [{"role": "system", "content": no_code}] + list(messages)
    except Exception as e:
        logging.warning(f"[V3_CALL_API_ASYNC] context enhance: {type(e).__name__}: {e}")
    return await http_caller.call_api_async(
        backend, messages, max_tokens, system_prompt=sys_prompt, ide=ide)
