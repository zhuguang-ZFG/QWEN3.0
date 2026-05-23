"""routes/anthropic_stream.py — Anthropic Messages API 流式处理器

从 server.py 提取的 Anthropic SSE 流式生成器:
- anthropic_stream_passthrough: 图片请求的 passthrough 流式
- anthropic_stream: 主 Anthropic 流式处理（路由 + fallback + 质量门）
"""
import json
import time
import uuid
import asyncio
import os

import smart_router
import routing_engine
import http_caller
import health_tracker
from orchestrate import orchestrate, needs_orchestration
from response_builder import extract_query, messages_to_dicts
from routes.quality_gate import (
    quality_check, default_route, get_same_tier_backends,
    get_upgrade_chain, try_backend,
)
from routes.stream_handlers import speculative_stream_chunks
from routes.images import build_pollinations_url

# ── Injected dependencies (set by server.py at import time) ──────────────────
_last_resort_call = None
_thinking_route = None
_record_request = None
_extract_system_prompt = None
_log_sys_prompt = None


def inject_deps(*, last_resort_call, thinking_route, record_request,
                extract_system_prompt, log_sys_prompt):
    """Called by server.py to inject functions that live there."""
    global _last_resort_call, _thinking_route, _record_request
    global _extract_system_prompt, _log_sys_prompt
    _last_resort_call = last_resort_call
    _thinking_route = thinking_route
    _record_request = record_request
    _extract_system_prompt = extract_system_prompt
    _log_sys_prompt = log_sys_prompt


async def anthropic_stream_passthrough(body: dict, model: str):
    """含图片时：转发给视觉模型，流式返回。"""
    query_text = ""
    for m in body.get("messages", []):
        c = m.get("content", "")
        if isinstance(c, list):
            query_text = " ".join(b.get("text", "") for b in c if b.get("type") == "text")
        elif isinstance(c, str):
            query_text = c

    content = (
        f"[图片分析] 收到包含图片的请求。当前视觉模型暂未接入，"
        f"请用文字描述图片内容后重新提问。\n\n你的文字描述：{query_text}"
        if query_text
        else "[图片分析] 收到图片请求，请附带文字描述以便分析。"
    )

    msg_id = f"msg_{uuid.uuid4().hex[:24]}"
    yield f"event: message_start\ndata: {json.dumps({'type':'message_start','message':{'id':msg_id,'type':'message','role':'assistant','model':model,'content':[],'stop_reason':None,'stop_sequence':None,'usage':{'input_tokens':10,'output_tokens':0}}})}\n\n"
    yield f"event: content_block_start\ndata: {json.dumps({'type':'content_block_start','index':0,'content_block':{'type':'text','text':''}})}\n\n"

    chunk_size = 30
    for i in range(0, len(content), chunk_size):
        chunk = content[i:i+chunk_size]
        yield f"event: content_block_delta\ndata: {json.dumps({'type':'content_block_delta','index':0,'delta':{'type':'text_delta','text':chunk}}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.01)

    yield f"event: content_block_stop\ndata: {json.dumps({'type':'content_block_stop','index':0})}\n\n"
    yield f"event: message_delta\ndata: {json.dumps({'type':'message_delta','delta':{'stop_reason':'end_turn','stop_sequence':None},'usage':{'output_tokens':len(content)//4}})}\n\n"
    yield f"event: message_stop\ndata: {json.dumps({'type':'message_stop'})}\n\n"


async def anthropic_stream(req, model: str, client_ip: str = "",
                           ide_source: str = "", sys_prompt_preview: str = ""):
    """Anthropic SSE 流式响应（真流式透传 + fallback）。"""
    query = extract_query(req.messages)
    t0 = time.time()

    # ── Image generation intent detection ──────────────────────────────────
    is_image, image_prompt = smart_router.detect_image_intent(query)
    if is_image:
        image_url = build_pollinations_url(image_prompt, "1024x1024")
        content = f"![image]({image_url})\n\n已为您生成图片，点击查看。"
        backend_used = "pollinations"
        duration_ms = int((time.time() - t0) * 1000)
        _record_request(query, backend_used, "image_generation", duration_ms, True,
                        client_ip=client_ip, ide_source=ide_source, sys_prompt_preview=sys_prompt_preview)
        msg_id = f"msg_{uuid.uuid4().hex[:24]}"
        yield f"event: message_start\ndata: {json.dumps({'type':'message_start','message':{'id':msg_id,'type':'message','role':'assistant','model':model,'content':[],'stop_reason':None,'stop_sequence':None,'usage':{'input_tokens':10,'output_tokens':0}}})}\n\n"
        yield f"event: content_block_start\ndata: {json.dumps({'type':'content_block_start','index':0,'content_block':{'type':'text','text':''}})}\n\n"
        yield f"event: content_block_delta\ndata: {json.dumps({'type':'content_block_delta','index':0,'delta':{'type':'text_delta','text':content}}, ensure_ascii=False)}\n\n"
        yield f"event: content_block_stop\ndata: {json.dumps({'type':'content_block_stop','index':0})}\n\n"
        yield f"event: message_delta\ndata: {json.dumps({'type':'message_delta','delta':{'stop_reason':'end_turn','stop_sequence':None},'usage':{'output_tokens':len(content)//4}})}\n\n"
        yield f"event: message_stop\ndata: {json.dumps({'type':'message_stop'})}\n\n"
        return

    # ── Deep Thinking Mode Detection ────────────────────────────────────────
    use_thinking = getattr(req, 'thinking', False) or smart_router.detect_thinking_intent(query)
    thinking_handled = False
    if use_thinking:
        thinking_result = await _thinking_route(query, req.max_tokens or 4096, ide_source)
        if thinking_result:
            content = thinking_result["answer"]
            backend_used = thinking_result["backend"]
            intent_used = "thinking"
            thinking_handled = True

    if not thinking_handled:
        # ── Normal routing ─────────────────────────────────────────────────
        intent_used = smart_router.analyze(query, system_prompt=sys_prompt_preview, ide=ide_source)
        use_orch = needs_orchestration(query, intent_used)
        intent_name = intent_used.get("intent", "unknown") if isinstance(intent_used, dict) else "unknown"
        complexity = intent_used.get("complexity", 0.5) if isinstance(intent_used, dict) else 0.5

        if use_orch:
            result = await asyncio.to_thread(orchestrate, query)
            content = result.get("answer", "")
            backend_used = result.get("backend", "orchestrator")
            thinking_handled = False  # use fake stream path below
        else:
            # SPECULATIVE STREAMING: predict backend + stream in parallel
            msg_id = f"msg_{uuid.uuid4().hex[:24]}"
            total_text = ""
            yield f"event: message_start\ndata: {json.dumps({'type':'message_start','message':{'id':msg_id,'type':'message','role':'assistant','model':model,'content':[],'stop_reason':None,'stop_sequence':None,'usage':{'input_tokens':10,'output_tokens':0}}})}\n\n"
            yield f"event: content_block_start\ndata: {json.dumps({'type':'content_block_start','index':0,'content_block':{'type':'text','text':''}})}\n\n"
# ── PLACEHOLDER_SPECULATIVE_CONT ──
            streamed_any = False
            async for backend_used, chunk in speculative_stream_chunks(
                    query, messages_to_dicts(req.messages), req.max_tokens or 4096, ide_source):
                streamed_any = True
                total_text += chunk
                yield f"event: content_block_delta\ndata: {json.dumps({'type':'content_block_delta','index':0,'delta':{'type':'text_delta','text':chunk}}, ensure_ascii=False)}\n\n"

            if streamed_any and not quality_check(total_text, complexity, backend_used, query=query):
                health_tracker.record_response_quality(backend_used, len(total_text), is_error_msg=True)

            if not streamed_any:
                # Fallback: use routing_engine with full fallback chain
                try:
                    backends = routing_engine.select(
                        "ide" if ide_source else "chat",
                        health_tracker.get_health_map())
                    fb_backend, fb_answer, _ = await asyncio.to_thread(
                        routing_engine.execute, backends,
                        lambda b, m, t: http_caller.call_api(b, m, t,
                            system_prompt=sys_prompt_preview, ide=ide_source),
                        messages_to_dicts(req.messages), req.max_tokens or 4096)
                    fallback_text = fb_answer if fb_answer and fb_backend != "exhausted" else None
                except Exception:
                    fallback_text = None
                    fb_backend = "fallback_error"
                backend_used = fb_backend if fallback_text else "last_resort"
                if fallback_text and not quality_check(fallback_text, complexity, fb_backend, query=query):
                    health_tracker.record_response_quality(fb_backend, len(fallback_text), is_error_msg=True)
                    fallback_text = None
                    backend_used = "last_resort"
                if fallback_text:
                    total_text = fallback_text
                    chunk_size = 30
                    for i in range(0, len(fallback_text), chunk_size):
                        chunk = fallback_text[i:i+chunk_size]
                        yield f"event: content_block_delta\ndata: {json.dumps({'type':'content_block_delta','index':0,'delta':{'type':'text_delta','text':chunk}}, ensure_ascii=False)}\n\n"
                        await asyncio.sleep(0.01)
                else:
                    total_text = _last_resort_call(messages_to_dicts(req.messages)) or "系统维护中，请稍后重试。"
                    yield f"event: content_block_delta\ndata: {json.dumps({'type':'content_block_delta','index':0,'delta':{'type':'text_delta','text':total_text}}, ensure_ascii=False)}\n\n"

            # End events
            yield f"event: content_block_stop\ndata: {json.dumps({'type':'content_block_stop','index':0})}\n\n"
            yield f"event: message_delta\ndata: {json.dumps({'type':'message_delta','delta':{'stop_reason':'end_turn','stop_sequence':None},'usage':{'output_tokens':len(total_text)//4}})}\n\n"
            yield f"event: message_stop\ndata: {json.dumps({'type':'message_stop'})}\n\n"

            duration_ms = int((time.time() - t0) * 1000)
            record_intent = intent_used if isinstance(intent_used, str) else intent_name
            _record_request(query, backend_used, record_intent, duration_ms, True,
                            client_ip=client_ip, ide_source=ide_source, sys_prompt_preview=sys_prompt_preview)
            _do_logging(req, query, total_text, record_intent, backend_used)
            return
# ── PLACEHOLDER_FAKE_STREAM ──
        # ── Fake stream path: thinking mode, orchestration, or fallback ────
        if not quality_check(content, complexity, backend_used, query=query):
            fallback_backend = default_route(query, ide_source) if backend_used == "unknown" else backend_used
            same_tier = get_same_tier_backends(fallback_backend)
            fallback_found = False
            for alt in same_tier:
                alt_result = await try_backend(
                    alt, query, req.max_tokens or 4096,
                    messages=messages_to_dicts(req.messages),
                )
                if alt_result and quality_check(alt_result["answer"], complexity, alt, query=query):
                    content = alt_result["answer"]
                    backend_used = alt
                    fallback_found = True
                    break
            if not fallback_found:
                upgrade_chain = get_upgrade_chain(fallback_backend)
                for upgraded in upgrade_chain:
                    up_result = await try_backend(
                        upgraded, query, req.max_tokens or 4096,
                        messages=messages_to_dicts(req.messages),
                    )
                    if up_result and quality_check(up_result["answer"], complexity, upgraded, query=query):
                        content = up_result["answer"]
                        backend_used = upgraded
                        fallback_found = True
                        break
            if not fallback_found and not content:
                content = "当前所有服务暂时不可用，请稍后重试。"
                backend_used = "fallback_exhausted"

    # ── Build fake stream for thinking/orchestration/fallback ─────────────
    duration_ms = int((time.time() - t0) * 1000)
    record_intent = intent_used if isinstance(intent_used, str) else (
        intent_used.get("intent", "unknown") if isinstance(intent_used, dict) else "unknown")
    _record_request(query, backend_used, record_intent, duration_ms, True,
                    client_ip=client_ip, ide_source=ide_source, sys_prompt_preview=sys_prompt_preview)

    if not content or not content.strip():
        content = _last_resort_call(messages_to_dicts(req.messages)) or "系统维护中，请稍后重试。"
        backend_used = backend_used or "empty_response"

    msg_id = f"msg_{uuid.uuid4().hex[:24]}"
    yield f"event: message_start\ndata: {json.dumps({'type':'message_start','message':{'id':msg_id,'type':'message','role':'assistant','model':model,'content':[],'stop_reason':None,'stop_sequence':None,'usage':{'input_tokens':10,'output_tokens':0}}})}\n\n"
    yield f"event: content_block_start\ndata: {json.dumps({'type':'content_block_start','index':0,'content_block':{'type':'text','text':''}})}\n\n"

    chunk_size = 20
    for i in range(0, len(content), chunk_size):
        chunk = content[i:i+chunk_size]
        yield f"event: content_block_delta\ndata: {json.dumps({'type':'content_block_delta','index':0,'delta':{'type':'text_delta','text':chunk}}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.01)

    yield f"event: content_block_stop\ndata: {json.dumps({'type':'content_block_stop','index':0})}\n\n"
    yield f"event: message_delta\ndata: {json.dumps({'type':'message_delta','delta':{'stop_reason':'end_turn','stop_sequence':None},'usage':{'output_tokens':len(content)//4}})}\n\n"
    yield f"event: message_stop\ndata: {json.dumps({'type':'message_stop'})}\n\n"

    _do_logging(req, query, content, record_intent, backend_used)


def _do_logging(req, query, content, record_intent, backend_used):
    """Shared logging for sys_prompt capture and distill queue."""
    sys_prompt = _extract_system_prompt(req.messages)
    if sys_prompt:
        try:
            _log_sys_prompt(sys_prompt)
        except Exception:
            pass
    try:
        if os.environ.get("DISTILL_LOG", "0") == "1":
            smart_router._log_to_distill_queue(query, content, record_intent, backend_used)
    except Exception:
        pass
