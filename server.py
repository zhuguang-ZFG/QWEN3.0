"""server.py — LiMa（力码）OpenAI 兼容接口层
让 Cursor、Claude Code、VS Code Copilot 等 AI IDE 直接接入。
支持流式/非流式 ChatCompletion，兼容 OpenAI API 格式。
"""
import sys, os, json, time, uuid, asyncio, threading, functools, logging
from typing import Optional, Union
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Request, HTTPException, Depends, Header
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse
from pydantic import BaseModel, Field, field_validator
import uvicorn

from access_guard import require_private_api_key
import smart_router
from orchestrate import orchestrate, needs_orchestration
from vision_handler import (
    _vision_route, _stream_vision_response,
    detect_vision_request, convert_openai_vision_to_anthropic,
)
from converters.anthropic_format import (
    convert_tools_anthropic_to_openai as _convert_tools_anthropic_to_openai,
    convert_messages_anthropic_to_openai as _convert_messages_anthropic_to_openai,
    anthropic_system_text as _anthropic_system_text,
    last_openai_user_text as _last_openai_user_text,
    inject_anthropic_context_preflight as _inject_anthropic_context_preflight,
    anthropic_text_fallback as _anthropic_text_fallback,
    normalize_openai_text as _normalize_openai_text,
    convert_response_openai_to_anthropic as _convert_response_openai_to_anthropic,
)


def _last_resort_call(messages: list) -> str:
    """Nuclear fallback: direct Cloudflare call, bypasses all routing/health logic."""
    import urllib.request, logging
    account_id = os.environ.get('CLOUDFLARE_ACCOUNT_ID', '')
    token = os.environ.get('CLOUDFLARE_TOKEN', '')
    if not account_id or not token:
        return ""
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1/chat/completions"
    body = json.dumps({"model": "@cf/meta/llama-3.3-70b-instruct-fp8-fast", "messages": messages[-5:], "max_tokens": 4096}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        data = json.loads(resp.read().decode())
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception as e:
        logging.warning(f"[LAST_RESORT] Cloudflare fallback failed: {type(e).__name__}")
        return ""

# ── V3 路由引擎 ──────────────────────────────────────────────────────────────
import routing_engine
import http_caller
import health_tracker
import streaming as streaming_mod
from routes.v3_adapters import (
    v3_route, v3_predict, v3_select, v3_call_stream, v3_call_api, fake_stream,
    FAKE_STREAM_BACKENDS,
)
from routes.quality_gate import (
    quality_check, allows_short_direct_answer, expected_direct_answer,
    get_same_tier_backends, get_upgrade_chain, default_route,
    try_backend, honest_failure_response,
    BACKEND_TIERS, EXACT_OUTPUT_MARKERS,
)

# ── App ─────────────────────────────────────────────────────────────────────
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(application):
    """FastAPI lifespan: 启动/关闭时执行。"""
    import probe_loop
    probe_loop.start(probe_fn=http_caller.probe)
    try:
        from session_memory.daemon import start_daemon
        await start_daemon()
    except ImportError:
        pass
    yield
    import probe_loop
    probe_loop.stop()
    try:
        from session_memory.daemon import stop_daemon
        stop_daemon()
    except ImportError:
        pass

app = FastAPI(title="LiMa", version="1.3",
              description="LiMa（力码）— 智能编程助手 API，OpenAI 兼容",
              lifespan=lifespan)

MAX_BODY_SIZE = 2 * 1024 * 1024  # 2MB (coding assistant 上下文可能较大)

@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_BODY_SIZE:
                return JSONResponse(status_code=413, content={"error": {"message": "Request body too large"}})
        except ValueError:
            return JSONResponse(status_code=400, content={"error": {"message": "Invalid Content-Length"}})
    return await call_next(request)

MODEL_ID = "lima-1.3"
MODEL_CREATED = int(time.time())

# ── 统计收集器 ─────────────────────────────────────────────────────────────────
_stats_lock = threading.Lock()
_stats = {
    "total_requests": 0,
    "backend_calls": {},
    "intent_distribution": {},
    "recent_logs": [],
    "start_time": time.time(),
}

# 后端启用/禁用状态
_backend_enabled = {}

# ── Request Tracking (extracted to routes/request_tracking.py) ────────────────
import routes.request_tracking as _rt_mod
_rt_mod.inject_state(_stats, _stats_lock)
_record_fallback = _rt_mod.record_fallback
_record_request = _rt_mod.record_request
_get_ip_location = _rt_mod.get_ip_location
_client_ip = _rt_mod.client_ip
_detect_ide = _rt_mod.detect_ide
_elapsed_ms = _rt_mod.elapsed_ms
FALLBACK_LOG = _rt_mod.FALLBACK_LOG


# ── Pydantic Models ─────────────────────────────────────────────────────────
class Message(BaseModel):
    role: str
    content: Union[str, list] = ""


class ChatRequest(BaseModel):
    model: str = MODEL_ID
    messages: list[Message]
    stream: bool = False
    max_tokens: Optional[int] = Field(default=1024, alias="max_tokens")
    temperature: Optional[float] = 0.7
    thinking: Optional[bool] = False


# ── Helpers (imported from response_builder.py) ────────────────────────────────
from response_builder import (
    make_chat_id, build_response, build_stream_chunk,
    build_anthropic_response, extract_query, messages_to_dicts,
)


# ── Deep Thinking Mode Helper ─────────────────────────────────────────────────
async def _thinking_route(query: str, max_tokens: int = 4096, ide: str = "unknown") -> dict | None:
    """Route to a thinking-capable backend. Returns result dict or None on failure."""
    thinking_backend = smart_router.get_thinking_backend()
    msgs = [{"role": "user", "content": query}]
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(smart_router.call_api, thinking_backend, msgs, max_tokens, ide),
            timeout=90.0  # thinking models need more time
        )
        if result and not (isinstance(result, str) and (result.startswith("[ERR]") or "暂时不可用" in result)):
            return {"answer": result, "backend": thinking_backend, "thinking_mode": True}
    except (asyncio.TimeoutError, Exception) as e:
        if smart_router.DEBUG:
            print(f"[THINKING] {thinking_backend} failed: {e}", file=sys.stderr)
    # Try fallback thinking backends
    for alt in smart_router.THINKING_BACKENDS:
        if alt == thinking_backend:
            continue
        if alt not in smart_router.BACKENDS or not smart_router.BACKENDS[alt].get('key'):
            continue
        if not smart_router.cb_allow(alt):
            continue
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(smart_router.call_api, alt, msgs, max_tokens, ide),
                timeout=90.0
            )
            if result and not (isinstance(result, str) and (result.startswith("[ERR]") or "暂时不可用" in result)):
                return {"answer": result, "backend": alt, "thinking_mode": True}
        except (asyncio.TimeoutError, Exception):
            continue
    return None


# ── Vision routing now in vision_handler.py ──────────────────────────────────


def extract_system_prompt(messages: list[Message]) -> str | None:
    """提取 system prompt（如果存在）。"""
    for msg in messages:
        if msg.role == "system" and msg.content:
            return msg.content
    return None


def _log_sys_prompt(sys_prompt: str) -> None:
    """记录新的系统提示词。用 SHA256 去重，只记录未见过的。"""
    import hashlib
    os.makedirs(smart_router.DISTILL_QUEUE_DIR.replace("pending", "sys_prompts"), exist_ok=True)
    phash = hashlib.sha256(sys_prompt.encode()).hexdigest()[:16]
    sys_prompt_dir = os.path.join(os.path.dirname(smart_router.DISTILL_QUEUE_DIR), "sys_prompts")

    # 检查是否已存在
    existing = os.listdir(sys_prompt_dir) if os.path.exists(sys_prompt_dir) else []
    if any(phash in f for f in existing):
        return  # 已记录过

    # 推断 IDE 来源
    ide_source = "unknown"
    ide_markers = {"Claude Code": "claude_code", "Cursor": "cursor", "You are Cursor": "cursor",
                   "GitHub Copilot": "copilot", "Codex": "codex", "Windsurf": "windsurf"}
    for marker, source in ide_markers.items():
        if marker in sys_prompt:
            ide_source = source
            break

    entry = {
        "ide_source": ide_source,
        "prompt_hash": phash,
        "prompt_preview": sys_prompt[:500],
        "prompt_length": len(sys_prompt),
        "logged_at": __import__('datetime').datetime.now().isoformat(),
    }
    fname = os.path.join(sys_prompt_dir, f"{ide_source}_{phash}.json")
    with open(fname, 'w', encoding='utf-8') as _f:
        __import__('json').dump(entry, _f, ensure_ascii=False, indent=2)
    if smart_router.DEBUG:
        print(f"[SYS_PROMPT] new: {ide_source} ({len(sys_prompt)} chars)", file=sys.stderr)


# ── Tool Call Forwarding (extracted to routes/tool_forward.py) ─────────────────
import urllib.parse as _urllib_parse
import routes.tool_forward as _tool_fwd
_tool_fwd.inject_state(_record_request, MODEL_ID)
_anthropic_native_forward = _tool_fwd.anthropic_native_forward
_anthropic_native_stream = _tool_fwd.anthropic_native_stream
_simulate_anthropic_sse = _tool_fwd.simulate_anthropic_sse
_tool_call_forward = _tool_fwd.tool_call_forward
_tool_call_stream = _tool_fwd.tool_call_stream
_pick_tool_backend = _tool_fwd.pick_tool_backend
_iter_tool_backends = _tool_fwd.iter_tool_backends
TOOL_TIER1_BACKENDS = _tool_fwd.TOOL_TIER1_BACKENDS
ANTHROPIC_NATIVE_BACKENDS = _tool_fwd.ANTHROPIC_NATIVE_BACKENDS


# ── Image Generation (extracted to routes/images.py) ──────────────────────────
from routes.images import router as images_router, build_pollinations_url as _build_pollinations_url
import routes.images as _images_mod
_images_mod.inject_record_request(_record_request)
app.include_router(images_router)


# ── Routes ──────────────────────────────────────────────────────────────────
@app.post(
    "/v1/chat/completions",
    dependencies=[Depends(require_private_api_key)],
)
async def chat_completions(request: Request):
    """OpenAI 兼容接口。"""
    body = await request.json()
    raw_messages = body.get("messages", [])
    # Support explicit thinking flag from request body
    client_ip = _client_ip(request)
    ide_source = _detect_ide(raw_messages)

    # Rate limiting (IDE clients get higher quota, not exempt)
    import rate_limiter
    rate_limit_multiplier = 5 if ide_source else 1
    if not rate_limiter.check_rate_limit(client_ip, multiplier=rate_limit_multiplier):
        return JSONResponse(
            status_code=429,
            content={"error": {"message": "Rate limit exceeded. Try again later.", "type": "rate_limit_error"}})

    sys_prompt_preview = ""
    for m in raw_messages:
        if isinstance(m, dict) and m.get("role") == "system":
            sys_prompt_preview = (m.get("content", "") if isinstance(m.get("content"), str) else "")[:200]
            break

    # ── Vision detection on raw messages (before Pydantic parsing) ────────
    if detect_vision_request(raw_messages):
        chat_id = make_chat_id()
        t0 = time.time()
        # Extract text query for logging
        query_text = ""
        for m in reversed(raw_messages):
            if m.get("role") == "user":
                c = m.get("content", "")
                if isinstance(c, str):
                    query_text = c
                elif isinstance(c, list):
                    query_text = " ".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
                break
        vision_result = await _vision_route(raw_messages, body.get("max_tokens", 4096), ide_source)
        if vision_result:
            content = vision_result["answer"]
            backend = vision_result["backend"]
            duration_ms = int((time.time() - t0) * 1000)
            _record_request(query_text or "[vision]", backend, "vision", duration_ms, True, client_ip=client_ip, ide_source=ide_source, sys_prompt_preview=sys_prompt_preview)
            if body.get("stream", False):
                return StreamingResponse(
                    _stream_vision_response(chat_id, content),
                    media_type="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
                )
            return JSONResponse(build_response(chat_id, content, backend, duration_ms))

    req = ChatRequest(**body)
    if body.get("thinking", False):
        req.thinking = True
    return await _handle_chat(req, fmt="openai", client_ip=client_ip, ide_source=ide_source, sys_prompt_preview=sys_prompt_preview)


@app.post("/v1/messages", dependencies=[Depends(require_private_api_key)])
async def anthropic_messages(req: Request):
    """Anthropic 兼容接口（供 cc-switch Claude Code 使用）。支持流式和非流式、多模态。"""
    request_started_at = time.time()
    body = await req.json()

    # ── Rate limiting (consistent with OpenAI endpoint) ───────────────────
    client_ip = _client_ip(req)
    import rate_limiter
    ua = req.headers.get("user-agent", "")
    is_ide_client = any(k in ua.lower() for k in ("claude-code", "continue", "cursor", "copilot"))
    rate_limit_multiplier = 5 if is_ide_client else 1
    if not rate_limiter.check_rate_limit(client_ip, multiplier=rate_limit_multiplier):
        return JSONResponse(
            status_code=429,
            content={"type": "error", "error": {"type": "rate_limit_error", "message": "Rate limit exceeded. Try again later."}})

    # ── 提取用户查询，先检查预设直答 ──────────────────────────────────────────
    raw_messages = body.get("messages", [])
    last_user_query = ""
    for msg in reversed(raw_messages):
        if isinstance(msg, dict) and msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                last_user_query = content
            elif isinstance(content, list):
                last_user_query = " ".join(b.get("text", "") for b in content if b.get("type") == "text")
            break

    # ── 工具调用检测：有 tools 定义就直接转发给 Anthropic 后端 ─────────────────
    if body.get("tools"):
        is_stream = body.get("stream", False)
        if is_stream:
            return StreamingResponse(
                _anthropic_native_stream(body),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
            )
        else:
            result = await _anthropic_native_forward(body)
            return JSONResponse(result)

    has_image = False

    # 解析消息：支持纯文本和多模态数组格式
    messages = []
    for m in raw_messages:
        role = m.get("role", "")
        if role not in ("user", "assistant"):
            continue
        content = m.get("content", "")
        if isinstance(content, str):
            messages.append(Message(role=role, content=content))
        elif isinstance(content, list):
            # 多模态：提取文本，检测图片
            text_parts = []
            for block in content:
                if block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
                elif block.get("type") == "image":
                    has_image = True
            messages.append(Message(role=role, content="\n".join(text_parts) if text_parts else "[图片]"))

    # system prompt
    if body.get("system"):
        if isinstance(body["system"], str):
            messages.insert(0, Message(role="system", content=body["system"]))
        elif isinstance(body["system"], list):
            txt = " ".join(b.get("text", "") for b in body["system"] if b.get("type") == "text")
            if txt:
                messages.insert(0, Message(role="system", content=txt))

    req_model = body.get("model", MODEL_ID)
    is_stream = body.get("stream", False)

    # 用户追踪信息
    client_ip = req.headers.get("x-forwarded-for", "").split(",")[0].strip() or (req.client.host if req.client else "")
    ide_source = _detect_ide(raw_messages)
    sys_prompt_preview = ""
    for m in raw_messages:
        if isinstance(m, dict) and m.get("role") == "system":
            sys_prompt_preview = (m.get("content", "") if isinstance(m.get("content"), str) else "")[:200]
            break
    if not sys_prompt_preview and body.get("system"):
        if isinstance(body["system"], str):
            sys_prompt_preview = body["system"][:200]
        elif isinstance(body["system"], list):
            sys_prompt_preview = " ".join(b.get("text", "") for b in body["system"] if b.get("type") == "text")[:200]

    # 含图片时：路由给视觉模型处理
    if has_image:
        # Build raw messages for vision routing (preserve image blocks)
        vision_msgs = []
        for m in raw_messages:
            if isinstance(m, dict) and m.get("role") in ("user", "assistant"):
                content = m.get("content", "")
                if isinstance(content, list):
                    # Convert Anthropic image blocks to OpenAI vision format for unified processing
                    openai_blocks = []
                    for block in content:
                        if block.get("type") == "text":
                            openai_blocks.append({"type": "text", "text": block.get("text", "")})
                        elif block.get("type") == "image":
                            source = block.get("source", {})
                            if source.get("type") == "base64":
                                media_type = source.get("media_type", "image/jpeg")
                                data = source.get("data", "")
                                openai_blocks.append({
                                    "type": "image_url",
                                    "image_url": {"url": f"data:{media_type};base64,{data}"}
                                })
                        else:
                            openai_blocks.append(block)
                    vision_msgs.append({"role": m["role"], "content": openai_blocks})
                else:
                    vision_msgs.append({"role": m["role"], "content": content})

        vision_result = await _vision_route(vision_msgs, body.get("max_tokens", 4096), ide_source)
        if vision_result:
            content_text = vision_result["answer"]
            backend_used = vision_result["backend"]
            duration_ms = _elapsed_ms(request_started_at)
            _record_request(last_user_query or "[vision]", backend_used, "vision", duration_ms, True, client_ip=client_ip, ide_source=ide_source, sys_prompt_preview=sys_prompt_preview)
            if is_stream:
                async def _vision_anthropic_stream():
                    msg_id = f"msg_{uuid.uuid4().hex[:24]}"
                    yield f"event: message_start\ndata: {json.dumps({'type':'message_start','message':{'id':msg_id,'type':'message','role':'assistant','model':req_model,'content':[],'stop_reason':None,'usage':{'input_tokens':10,'output_tokens':0}}})}\n\n"
                    yield f"event: content_block_start\ndata: {json.dumps({'type':'content_block_start','index':0,'content_block':{'type':'text','text':''}})}\n\n"
                    chunk_size = 30
                    for i in range(0, len(content_text), chunk_size):
                        chunk = content_text[i:i+chunk_size]
                        yield f"event: content_block_delta\ndata: {json.dumps({'type':'content_block_delta','index':0,'delta':{'type':'text_delta','text':chunk}}, ensure_ascii=False)}\n\n"
                        await asyncio.sleep(0.01)
                    yield f"event: content_block_stop\ndata: {json.dumps({'type':'content_block_stop','index':0})}\n\n"
                    yield f"event: message_delta\ndata: {json.dumps({'type':'message_delta','delta':{'stop_reason':'end_turn','stop_sequence':None},'usage':{'output_tokens':len(content_text)//4}})}\n\n"
                    yield f"event: message_stop\ndata: {json.dumps({'type':'message_stop'})}\n\n"
                return StreamingResponse(_vision_anthropic_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
            return JSONResponse(build_anthropic_response(f"msg_{uuid.uuid4().hex[:24]}", content_text, backend_used, req_model))
        # If vision routing failed, fall through to the old passthrough behavior
        if is_stream:
            return StreamingResponse(
                _anthropic_stream_passthrough(body, req_model),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
            )

    chat_req = ChatRequest(
        model=req_model.replace("[1m]", ""),
        messages=messages,
        stream=False,
        max_tokens=body.get("max_tokens", 4096)
    )

    if is_stream:
        return StreamingResponse(
            _anthropic_stream(chat_req, req_model, client_ip=client_ip, ide_source=ide_source, sys_prompt_preview=sys_prompt_preview),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
        )
    return await _handle_chat(chat_req, fmt="anthropic", request_model=req_model, client_ip=client_ip, ide_source=ide_source, sys_prompt_preview=sys_prompt_preview)


# ── Anthropic streaming (extracted to routes/anthropic_stream.py) ────────────
from routes.anthropic_stream import (
    anthropic_stream as _anthropic_stream,
    anthropic_stream_passthrough as _anthropic_stream_passthrough,
    inject_deps as _inject_anthropic_stream_deps,
)
_inject_anthropic_stream_deps(
    last_resort_call=_last_resort_call,
    thinking_route=_thinking_route,
    record_request=_record_request,
    extract_system_prompt=extract_system_prompt,
    log_sys_prompt=_log_sys_prompt,
)


async def _handle_chat(req: ChatRequest, fmt: str = "openai", request_model: str = None, client_ip: str = "", ide_source: str = "", sys_prompt_preview: str = ""):
    query = extract_query(req.messages)
    if not query.strip():
        raise HTTPException(status_code=400, detail="Empty query")

    # ── Integration: Guardrails (Phase 19) ────────────────────────────────
    try:
        from context_pipeline.guardrails import run_input_guardrails, GuardrailSeverity
        raw_messages = [{"role": m.role, "content": m.content} if hasattr(m, 'role') else m for m in req.messages]
        guard_result = run_input_guardrails(raw_messages)
        if not guard_result.passed and guard_result.severity == GuardrailSeverity.BLOCK:
            raise HTTPException(status_code=422, detail=f"Input blocked: {guard_result.violations}")
    except ImportError:
        pass

    chat_id = make_chat_id()
    t0 = time.time()

    # ── Integration: Tracing (Phase 22) ───────────────────────────────────
    try:
        from context_pipeline.tracing import new_trace
        trace = new_trace()
        trace.start_span("handle_chat", chat_id=chat_id, ide=ide_source)
    except ImportError:
        trace = None

    # ── Integration: Token Budget (Phase 21) ──────────────────────────────
    try:
        from context_pipeline.token_budget import check_budget, estimate_request_tokens
        raw_msgs = [{"role": m.role, "content": m.content} if hasattr(m, 'role') else m for m in req.messages]
        budget_status = check_budget(raw_msgs, sys_prompt_preview or "", "coding" if ide_source else "chat")
        if not budget_status["within_budget"] and budget_status["action"] == "truncate_context":
            if len(req.messages) > 10:
                req.messages = req.messages[:3] + req.messages[-7:]
    except ImportError:
        pass

    # ── Integration: User Identity (Phase 7) ──────────────────────────────
    try:
        from user_identity.adapter import adapt_system_prompt
        _adapted = adapt_system_prompt(sys_prompt_preview or "", client_ip)
        if _adapted != sys_prompt_preview:
            sys_prompt_preview = _adapted
    except ImportError:
        pass

    # ── Mode-based routing preference ─────────────────────────────────────
    prefer = None
    if req.model in ("fast", "lima"):
        prefer = "longcat_lite"
    elif req.model in ("expert", "lima-thinking"):
        prefer = "scnet_ds_pro"
        req.thinking = True
    elif req.model in ("code", "lima-code"):
        prefer = None  # handled by classify_scenario → code pool
        ide_source = ide_source or "chat_code_mode"
    elif req.model == "vision":
        prefer = None  # vision handled by existing detection

    # ── Image generation intent detection ──────────────────────────────────
    is_image, image_prompt = smart_router.detect_image_intent(query)
    if is_image:
        image_url = _build_pollinations_url(image_prompt, "1024x1024")
        content = f"![image]({image_url})\n\n已为您生成图片，点击查看。"
        duration_ms = int((time.time() - t0) * 1000)
        _record_request(query, "pollinations", "image_generation", duration_ms, True, client_ip=client_ip, ide_source=ide_source, sys_prompt_preview=sys_prompt_preview)
        if fmt == "anthropic":
            return JSONResponse(build_anthropic_response(chat_id, content, "pollinations", request_model or MODEL_ID))
        return JSONResponse(build_response(chat_id, content, "pollinations", duration_ms))

    # ── Deep Thinking Mode ──────────────────────────────────────────────────
    use_thinking = getattr(req, 'thinking', False) or smart_router.detect_thinking_intent(query)
    if use_thinking and not req.stream:
        thinking_result = await _thinking_route(query, req.max_tokens or 4096, ide_source)
        if thinking_result:
            content = thinking_result["answer"]
            backend = thinking_result["backend"]
            duration_ms = int((time.time() - t0) * 1000)
            _record_request(query, backend, "thinking", duration_ms, True, client_ip=client_ip, ide_source=ide_source, sys_prompt_preview=sys_prompt_preview)
            if fmt == "anthropic":
                resp = build_anthropic_response(chat_id, content, backend, request_model or MODEL_ID)
                return JSONResponse(resp)
            resp = build_response(chat_id, content, backend, duration_ms)
            resp["choices"][0]["message"]["thinking"] = True
            resp["x_lima_meta"]["thinking_mode"] = True
            return JSONResponse(resp)
        # Thinking backends all failed, fall through to normal routing

    # 判断是否需要编排模式
    intent = smart_router.analyze(query, system_prompt=sys_prompt_preview, ide=ide_source)
    use_orchestration = needs_orchestration(query, intent) if not prefer else False

    if req.stream:
        return StreamingResponse(
            _stream_response(chat_id, query, use_orchestration, ide_source=ide_source, sys_prompt_preview=sys_prompt_preview, use_thinking=use_thinking, messages=messages_to_dicts(req.messages), prefer=prefer),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
        )

    # 非流式：直接调用（带 fallback）
    if use_orchestration:
        result = await asyncio.to_thread(orchestrate, query)
    else:
        result = await asyncio.to_thread(v3_route, query,
            messages_to_dicts(req.messages),
            system_prompt=sys_prompt_preview, ide=ide_source,
            max_tokens=req.max_tokens or 4096)

    content = result.get("answer", "")
    backend = result.get("backend", "unknown")
    total_ms = result.get("total_ms", 0)
    intent_name = intent.get("intent", "unknown") if isinstance(intent, dict) else "unknown"
    complexity = intent.get("complexity", 0.5) if isinstance(intent, dict) else 0.5

    # ── Fallback 层：质量检查 + 同层降级 + 跨层升级 ──
    if not quality_check(content, complexity, backend, query=query):
        fallback_intent = intent_name if intent_name != "unknown" else "unknown"
        fallback_backend = default_route(query, ide_source) if backend == "unknown" else backend

        # 同层降级：找同层级的其他后端
        same_tier = get_same_tier_backends(fallback_backend)
        for alt in same_tier:
            alt_result = await try_backend(
                alt,
                query,
                req.max_tokens or 1024,
                messages=messages_to_dicts(req.messages),
            )
            if alt_result and quality_check(alt_result["answer"], complexity, alt, query=query):
                content = alt_result["answer"]
                backend = alt
                _record_fallback(query, fallback_backend, alt, f"fallback_same_tier_{fallback_intent}", ide_source)
                _record_request(query, backend, f"fallback_same_tier_{fallback_intent}", int((time.time() - t0) * 1000), True, client_ip=client_ip, ide_source=ide_source, sys_prompt_preview=sys_prompt_preview)
                if fmt == "anthropic":
                    return JSONResponse(build_anthropic_response(chat_id, content, backend, request_model or MODEL_ID))
                return JSONResponse(build_response(chat_id, content, backend, int((time.time() - t0) * 1000)))

        # 跨层升级：逐级升级
        upgrade_chain = get_upgrade_chain(fallback_backend)
        for upgraded in upgrade_chain:
            up_result = await try_backend(
                upgraded,
                query,
                req.max_tokens or 1024,
                messages=messages_to_dicts(req.messages),
            )
            if up_result and quality_check(up_result["answer"], complexity, upgraded, query=query):
                content = up_result["answer"]
                backend = upgraded
                _record_fallback(query, fallback_backend, upgraded, f"fallback_upgrade_{fallback_intent}", ide_source)
                _record_request(query, backend, f"fallback_upgrade_{fallback_intent}", int((time.time() - t0) * 1000), True, client_ip=client_ip, ide_source=ide_source, sys_prompt_preview=sys_prompt_preview)
                if fmt == "anthropic":
                    return JSONResponse(build_anthropic_response(chat_id, content, backend, request_model or MODEL_ID))
                return JSONResponse(build_response(chat_id, content, backend, int((time.time() - t0) * 1000)))

        # 全部失败：诚实告知
        duration_ms = int((time.time() - t0) * 1000)
        _record_request(query, "fallback_exhausted", f"fallback_exhausted_{fallback_intent}", duration_ms, False, client_ip=client_ip, ide_source=ide_source, sys_prompt_preview=sys_prompt_preview)
        return JSONResponse(honest_failure_response(chat_id, fmt, request_model))

    duration_ms = int((time.time() - t0) * 1000)

    # ── Integration: Session Memory (Phase P1) — save to SQLite ───────────
    try:
        from session_memory.store import save_memory
        import hashlib
        _session_id = hashlib.md5((client_ip or "anon").encode()).hexdigest()[:12]
        save_memory(_session_id, "user", query[:100])
        if content:
            save_memory(_session_id, "assistant", content[:100])
        # ── Integration: AI Compactor (Phase 8) — compress if over threshold
        from session_memory.compactor import needs_compaction, compact_session
        if needs_compaction(_session_id):
            compact_session(_session_id)
    except (ImportError, Exception):
        pass

    # 记录统计
    _record_request(query, backend, intent_name, duration_ms, True, client_ip=client_ip, ide_source=ide_source, sys_prompt_preview=sys_prompt_preview)

    # 记录用户问答到 distill_queue（DISTILL_LOG=1 时启用）
    try:
        if os.environ.get("DISTILL_LOG", "0") == "1":
            smart_router._log_to_distill_queue(query, content, intent_name, backend)
    except Exception:
        pass

    # 记录系统提示词（去重）
    sys_prompt = extract_system_prompt(req.messages)
    if sys_prompt:
        try:
            _log_sys_prompt(sys_prompt)
        except Exception:
            pass

    if fmt == "anthropic":
        return JSONResponse(build_anthropic_response(chat_id, content, backend, request_model or MODEL_ID))
    return JSONResponse(build_response(chat_id, content, backend, total_ms))


# ── Streaming handlers (extracted to routes/stream_handlers.py) ───────────────
from routes.stream_handlers import real_stream_chunks, speculative_stream_chunks


async def _stream_response(chat_id: str, query: str, use_orchestration: bool, ide_source: str = "", sys_prompt_preview: str = "", use_thinking: bool = False, messages: list = None, prefer: str = None):
    """SSE 流式生成器：真流式透传后端 SSE 流。"""
    # ── Image generation intent detection ──────────────────────────────────
    is_image, image_prompt = smart_router.detect_image_intent(query)
    if is_image:
        image_url = _build_pollinations_url(image_prompt, "1024x1024")
        content = f"![image]({image_url})\n\n已为您生成图片，点击查看。"
        yield build_stream_chunk(chat_id, content)
        yield build_stream_chunk(chat_id, "", finish=True)
        yield "data: [DONE]\n\n"
        return

    # ── Thinking mode: uses special backends, keep fake stream for now ─────
    if use_thinking:
        thinking_result = await _thinking_route(query, 4096, ide_source)
        if thinking_result:
            content = thinking_result.get("answer", "")
            content = f"<think>\n{content}\n</think>"
        else:
            if use_orchestration:
                result = await asyncio.to_thread(orchestrate, query)
            else:
                result = await asyncio.to_thread(v3_route, query, messages,
                    system_prompt=sys_prompt_preview, ide=ide_source,
                    max_tokens=4096)
            content = result.get("answer", "") if isinstance(result, dict) else str(result)
        if not content or not content.strip():
            content = _last_resort_call(messages) or "系统维护中，请稍后重试。"
        sentences = _split_sentences(content)
        for sentence in sentences:
            yield build_stream_chunk(chat_id, sentence)
            await asyncio.sleep(0.02)
        yield build_stream_chunk(chat_id, "", finish=True)
        yield "data: [DONE]\n\n"
        return

    # ── Orchestration mode: keep fake stream (multi-step pipeline) ─────────
    if use_orchestration:
        result = await asyncio.to_thread(orchestrate, query)
        content = result.get("answer", "") if isinstance(result, dict) else str(result)
        if not content or not content.strip():
            content = _last_resort_call(messages) or "系统维护中，请稍后重试。"
        sentences = _split_sentences(content)
        for sentence in sentences:
            yield build_stream_chunk(chat_id, sentence)
            await asyncio.sleep(0.02)
        yield build_stream_chunk(chat_id, "", finish=True)
        yield "data: [DONE]\n\n"
        return

    # ── SPECULATIVE STREAMING: predict + stream in parallel with routing ──
    streamed_any = False
    async for backend, chunk in speculative_stream_chunks(query, messages, 4096, ide_source):
        streamed_any = True
        yield build_stream_chunk(chat_id, chunk)

    if not streamed_any:
        # All streaming failed, use routing_engine (has force-try logic)
        try:
            backends = routing_engine.select(
                "chat" if not ide_source else "ide",
                health_tracker.get_health_map())
            backend, answer, _ = await asyncio.to_thread(
                routing_engine.execute, backends,
                lambda b, m, t: http_caller.call_api(b, m, t),
                messages, 4096)
            content = answer if answer else ""
        except Exception:
            content = ""
        if not content or content.startswith('[ERR]'):
            content = _last_resort_call(messages) or "系统维护中，请稍后重试。"
        sentences = _split_sentences(content)
        for sentence in sentences:
            yield build_stream_chunk(chat_id, sentence)
            await asyncio.sleep(0.02)

    yield build_stream_chunk(chat_id, "", finish=True)
    yield "data: [DONE]\n\n"


def _split_sentences(text: str) -> list[str]:
    """将文本按句子/段落分割为流式 chunk。"""
    if not text:
        return [""]
    chunks = []
    current = ""
    for char in text:
        current += char
        if char in ("。", "！", "？", "\n", ".", "!", "?") and len(current) > 5:
            chunks.append(current)
            current = ""
    if current:
        chunks.append(current)
    return chunks if chunks else [text]


# ─── Embeddings 端点 (extracted to routes/embeddings.py) ──────────────────────
from routes.embeddings import router as embeddings_router
app.include_router(embeddings_router)


@app.get("/v1/models")
async def list_models():
    """返回模型列表，让 IDE 识别可用模型。"""
    models = [
        {"id": "claude-opus-4-7", "object": "model", "created": MODEL_CREATED, "owned_by": "anthropic"},
        {"id": "claude-sonnet-4", "object": "model", "created": MODEL_CREATED, "owned_by": "anthropic"},
        {"id": "claude-haiku-4", "object": "model", "created": MODEL_CREATED, "owned_by": "anthropic"},
        {"id": "gpt-5.4", "object": "model", "created": MODEL_CREATED, "owned_by": "openai"},
        {"id": "gpt-4.1", "object": "model", "created": MODEL_CREATED, "owned_by": "openai"},
        {"id": "o1", "object": "model", "created": MODEL_CREATED, "owned_by": "openai"},
        {"id": "o4-mini", "object": "model", "created": MODEL_CREATED, "owned_by": "openai"},
        {"id": "deepseek-v4-pro", "object": "model", "created": MODEL_CREATED, "owned_by": "deepseek"},
        {"id": "deepseek-v4-flash", "object": "model", "created": MODEL_CREATED, "owned_by": "deepseek"},
        {"id": "qwen3-coder", "object": "model", "created": MODEL_CREATED, "owned_by": "qwen"},
        {"id": "gemini-2.0-flash", "object": "model", "created": MODEL_CREATED, "owned_by": "google"},
        {"id": "llama-3.3-70b", "object": "model", "created": MODEL_CREATED, "owned_by": "meta"},
        {"id": MODEL_ID, "object": "model", "created": MODEL_CREATED, "owned_by": "donglicao"},
    ]
    return {"object": "list", "data": models}


@app.get("/health")
async def health():
    """健康检查端点。"""
    return {"status": "ok", "version": "2.0", "model": MODEL_ID}


@app.get("/api/live-key", dependencies=[Depends(require_private_api_key)])
async def live_key():
    """返回 Gemini Live API key（供视频通话前端使用）。"""
    key = os.environ.get("GOOGLE_AI_KEY", "")
    if not key:
        raise HTTPException(status_code=503, detail="Gemini key not configured")
    return {"key": key, "model": "models/gemini-2.0-flash-live-001"}


@app.get("/v1/status", dependencies=[Depends(require_private_api_key)])
async def router_status():
    """路由器状态：熔断器、后端列表、路由表。"""
    return {
        "circuit_breakers": smart_router.cb_status(),
        "backends": list(smart_router.BACKENDS.keys()),
        "route_table": smart_router.ROUTE,
        "public_model": smart_router.PUBLIC_MODEL_NAME
    }


# ── Admin routes (extracted to routes/admin.py) ────────────────────────────────
from routes.admin import router as admin_router
import routes.admin as _admin_mod
_admin_mod.inject_state(_stats, _stats_lock, _backend_enabled)
app.include_router(admin_router)

import routes.quality_gate as _qg_mod
_qg_mod.inject_state(_backend_enabled)

# ── MCP tools (knowledge/memory access for IDE clients) ───────────────────────
try:
    from lima_mcp.server import router as mcp_router
    app.include_router(mcp_router)
except ImportError:
    pass

# ── Agent task management APIs ───────────────────────────────────────────────
try:
    from routes.agent_tasks import router as agent_tasks_router
    app.include_router(agent_tasks_router)
except ImportError:
    pass

# ── Telegram Bot webhook ─────────────────────────────────────────────────────
try:
    from routes.telegram import router as telegram_router
    app.include_router(telegram_router)
except ImportError:
    pass


# ── Startup ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print('[LiMa] Warming up router model...', file=sys.stderr)
    smart_router.warmup_router_model()
    uvicorn.run(app, host="0.0.0.0", port=8080)
