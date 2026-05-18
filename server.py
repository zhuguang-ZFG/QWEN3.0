"""server.py — red V1flash OpenAI 兼容接口层
让 Cursor、Claude Code、VS Code Copilot 等 AI IDE 直接接入。
支持流式/非流式 ChatCompletion，兼容 OpenAI API 格式。
"""
import sys, os, json, time, uuid, asyncio, threading
from typing import Optional
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse
from pydantic import BaseModel, Field
import uvicorn

import smart_router
from orchestrate import orchestrate, needs_orchestration

# ── App ─────────────────────────────────────────────────────────────────────
app = FastAPI(title="red V1flash", version="2.0",
              description="CNC/Embedded AI Router — OpenAI Compatible API")

MODEL_ID = "red-v1flash"
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


def _record_request(query: str, backend: str, intent: str, duration_ms: int, success: bool = True):
    """记录一次请求到统计数据。"""
    with _stats_lock:
        _stats["total_requests"] += 1
        if backend not in _stats["backend_calls"]:
            _stats["backend_calls"][backend] = {"count": 0, "success": 0, "total_ms": 0}
        _stats["backend_calls"][backend]["count"] += 1
        if success:
            _stats["backend_calls"][backend]["success"] += 1
        _stats["backend_calls"][backend]["total_ms"] += duration_ms
        _stats["intent_distribution"][intent] = _stats["intent_distribution"].get(intent, 0) + 1
        log_entry = {
            "time": time.strftime("%H:%M:%S"),
            "query": query[:80],
            "backend": backend,
            "intent": intent,
            "ms": duration_ms,
            "success": success,
        }
        _stats["recent_logs"].append(log_entry)
        if len(_stats["recent_logs"]) > 100:
            _stats["recent_logs"] = _stats["recent_logs"][-100:]


# ── Pydantic Models ─────────────────────────────────────────────────────────
class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str = MODEL_ID
    messages: list[Message]
    stream: bool = False
    max_tokens: Optional[int] = Field(default=1024, alias="max_tokens")
    temperature: Optional[float] = 0.7


# ── Helpers ─────────────────────────────────────────────────────────────────
def make_chat_id() -> str:
    return f"chatcmpl-{uuid.uuid4().hex[:24]}"


def build_response(chat_id: str, content: str, backend: str, total_ms: int) -> dict:
    """构建 OpenAI ChatCompletion 非流式响应格式。"""
    return {
        "id": chat_id,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": MODEL_ID,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": content},
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        },
        "system_fingerprint": f"router_{backend}",
        "x_red_meta": {"backend": backend, "total_ms": total_ms}
    }


def build_stream_chunk(chat_id: str, content: str, finish: bool = False) -> str:
    """构建 SSE 流式 chunk。"""
    delta = {} if finish else {"content": content}
    chunk = {
        "id": chat_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": MODEL_ID,
        "choices": [{
            "index": 0,
            "delta": delta if not finish else {},
            "finish_reason": "stop" if finish else None
        }]
    }
    return f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"


def build_anthropic_response(msg_id: str, content: str, backend: str, model: str = MODEL_ID) -> dict:
    """构建 Anthropic Messages API 响应格式。"""
    return {
        "id": f"msg_{uuid.uuid4().hex[:24]}",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": [{"type": "text", "text": content}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": len(content) // 4},
    }


def extract_query(messages: list[Message]) -> str:
    """从 messages 列表提取最后一条 user 消息作为 query。"""
    for msg in reversed(messages):
        if msg.role == "user":
            return msg.content
    return messages[-1].content if messages else ""


# ── 快速直答（不调用任何后端，0ms）──────────────────────────────────────────
import re as _re
_INSTANT_REPLIES = [
    (_re.compile(r'你是什么|什么模型|who are you|what model|what are you|哪个模型|哪个公司|谁开发|谁训练|谁做的|哪家公司|什么公司|who made|who built|who created|介绍一下你|你的父亲|你的母亲|你的创造者|谁创造|你爸|你妈|你是谁', _re.IGNORECASE),
     "我是 red V1flash，由深圳市动力巢科技有限公司训练的AI模型。擅长编程开发、数据分析、技术方案设计、文档写作等领域，有什么可以帮你的？"),
    (_re.compile(r'调用工具|使用工具|call tool|use tool|能做什么|你的能力|你能干什么|有什么功能', _re.IGNORECASE),
     "我可以帮你：编写和调试代码、分析数据、设计技术方案、撰写文档、解答技术问题、数学推理等。直接描述你的需求即可。"),
    (_re.compile(r'处理图片|看图|识别图|分析图|图片|screenshot|image', _re.IGNORECASE),
     "目前暂不支持图片处理。请用文字描述图片内容或你的需求，我来帮你分析解决。"),
    (_re.compile(r'怎么实现.*路由|路由.*原理|怎么.*智能|智能路由.*怎么', _re.IGNORECASE),
     "我通过分析问题的类型和复杂度，自动从多个AI后端中选择最合适的模型来回答。简单问题用快速模型秒回，复杂问题用强推理模型深度分析，代码问题用代码专精模型生成。"),
    (_re.compile(r'^(hi|hello|hey|你好|嗨)[\s!！.。?？]*$', _re.IGNORECASE),
     "你好！我是 red V1flash，有什么可以帮你的？"),
]

def _try_instant_reply(query: str) -> str | None:
    """检查是否可以直接回答（不调用后端）。"""
    for pattern, reply in _INSTANT_REPLIES:
        if pattern.search(query.strip()):
            return reply
    return None


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
    __import__('json').dump(entry, open(fname, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    if smart_router.DEBUG:
        print(f"[SYS_PROMPT] new: {ide_source} ({len(sys_prompt)} chars)", file=sys.stderr)


# ── Tool Call Forwarding (DeepSeek R1 via OpenRouter) ─────────────────────────
import httpx as _httpx

TOOL_BACKEND_URL = "https://openrouter.ai/api/v1/chat/completions"
TOOL_BACKEND_MODEL = "deepseek/deepseek-r1-0528:free"
TOOL_BACKEND_KEY = os.environ.get("OPENROUTER_API_KEY", "")


def _convert_tools_anthropic_to_openai(tools: list) -> list:
    """Anthropic tools format -> OpenAI tools format."""
    openai_tools = []
    for tool in tools:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("input_schema", {})
            }
        })
    return openai_tools


def _convert_messages_anthropic_to_openai(messages: list) -> list:
    """Anthropic messages -> OpenAI messages (handles tool_use and tool_result)."""
    openai_msgs = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if isinstance(content, str):
            openai_msgs.append({"role": role, "content": content})
        elif isinstance(content, list):
            text_parts = []
            tool_calls = []
            tool_results = []
            for block in content:
                btype = block.get("type", "")
                if btype == "text":
                    text_parts.append(block.get("text", ""))
                elif btype == "tool_use":
                    tool_calls.append({
                        "id": block["id"],
                        "type": "function",
                        "function": {
                            "name": block["name"],
                            "arguments": json.dumps(block.get("input", {}))
                        }
                    })
                elif btype == "tool_result":
                    # Extract text content from tool_result
                    tr_content = block.get("content", "")
                    if isinstance(tr_content, list):
                        tr_content = "\n".join(
                            b.get("text", "") for b in tr_content
                            if b.get("type") == "text"
                        )
                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": block.get("tool_use_id", ""),
                        "content": str(tr_content)
                    })
            if tool_calls:
                openai_msgs.append({
                    "role": "assistant",
                    "content": "\n".join(text_parts) if text_parts else None,
                    "tool_calls": tool_calls
                })
            elif tool_results:
                for tr in tool_results:
                    openai_msgs.append(tr)
            else:
                openai_msgs.append({
                    "role": role,
                    "content": "\n".join(text_parts)
                })
    return openai_msgs


def _convert_response_openai_to_anthropic(openai_response: dict, model: str) -> dict:
    """OpenAI response -> Anthropic response (handles tool_calls)."""
    choice = openai_response["choices"][0]
    message = choice["message"]

    content = []
    if message.get("content"):
        content.append({"type": "text", "text": message["content"]})
    if message.get("tool_calls"):
        for tc in message["tool_calls"]:
            args_str = tc["function"].get("arguments", "{}")
            try:
                args = json.loads(args_str)
            except (json.JSONDecodeError, TypeError):
                args = {}
            content.append({
                "type": "tool_use",
                "id": tc.get("id", f"toolu_{uuid.uuid4().hex[:24]}"),
                "name": tc["function"]["name"],
                "input": args
            })

    usage = openai_response.get("usage", {})
    return {
        "id": f"msg_{uuid.uuid4().hex[:24]}",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": content,
        "stop_reason": "tool_use" if message.get("tool_calls") else "end_turn",
        "stop_sequence": None,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0)
        },
    }


async def _tool_call_forward(body: dict) -> dict:
    """Forward tool call request to DeepSeek R1 via OpenRouter."""
    openai_tools = _convert_tools_anthropic_to_openai(body["tools"])
    openai_messages = _convert_messages_anthropic_to_openai(body["messages"])

    # Add system prompt
    if body.get("system"):
        if isinstance(body["system"], str):
            sys_text = body["system"]
        else:
            sys_text = " ".join(
                b.get("text", "") for b in body["system"]
                if b.get("type") == "text"
            )
        openai_messages.insert(0, {"role": "system", "content": sys_text})

    payload = {
        "model": TOOL_BACKEND_MODEL,
        "messages": openai_messages,
        "tools": openai_tools,
        "max_tokens": body.get("max_tokens", 4096),
    }

    t0 = time.time()
    try:
        async with _httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                TOOL_BACKEND_URL,
                headers={
                    "Authorization": f"Bearer {TOOL_BACKEND_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            openai_resp = resp.json()
    except Exception as e:
        # Fallback: return error as text
        return {
            "id": f"msg_{uuid.uuid4().hex[:24]}",
            "type": "message",
            "role": "assistant",
            "model": body.get("model", MODEL_ID),
            "content": [{"type": "text", "text": f"[Tool backend error: {e}]"}],
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": 0, "output_tokens": 0},
        }

    duration_ms = int((time.time() - t0) * 1000)
    _record_request("tool_call", TOOL_BACKEND_MODEL, "tool_use", duration_ms, True)

    # Check for API error
    if "error" in openai_resp:
        err_msg = openai_resp["error"].get("message", str(openai_resp["error"]))
        return {
            "id": f"msg_{uuid.uuid4().hex[:24]}",
            "type": "message",
            "role": "assistant",
            "model": body.get("model", MODEL_ID),
            "content": [{"type": "text", "text": f"[Tool backend error: {err_msg}]"}],
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": 0, "output_tokens": 0},
        }

    return _convert_response_openai_to_anthropic(
        openai_resp, body.get("model", MODEL_ID)
    )


async def _tool_call_stream(body: dict):
    """Tool call streaming response (waits for full response, then simulates SSE)."""
    result = await _tool_call_forward(body)

    msg_id = result["id"]
    model = result["model"]

    # message_start
    yield f"event: message_start\ndata: {json.dumps({'type':'message_start','message':{'id':msg_id,'type':'message','role':'assistant','model':model,'content':[],'stop_reason':None,'stop_sequence':None,'usage':{'input_tokens':0,'output_tokens':0}}})}\n\n"

    for i, block in enumerate(result.get("content", [])):
        if block["type"] == "text":
            yield f"event: content_block_start\ndata: {json.dumps({'type':'content_block_start','index':i,'content_block':{'type':'text','text':''}})}\n\n"
            # Send text in chunks for smoother streaming
            text = block["text"]
            chunk_size = 40
            for j in range(0, len(text), chunk_size):
                chunk = text[j:j+chunk_size]
                yield f"event: content_block_delta\ndata: {json.dumps({'type':'content_block_delta','index':i,'delta':{'type':'text_delta','text':chunk}}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.01)
            yield f"event: content_block_stop\ndata: {json.dumps({'type':'content_block_stop','index':i})}\n\n"
        elif block["type"] == "tool_use":
            yield f"event: content_block_start\ndata: {json.dumps({'type':'content_block_start','index':i,'content_block':{'type':'tool_use','id':block['id'],'name':block['name']}})}\n\n"
            input_json = json.dumps(block["input"], ensure_ascii=False)
            yield f"event: content_block_delta\ndata: {json.dumps({'type':'content_block_delta','index':i,'delta':{'type':'input_json_delta','partial_json':input_json}})}\n\n"
            yield f"event: content_block_stop\ndata: {json.dumps({'type':'content_block_stop','index':i})}\n\n"

    stop_reason = result.get("stop_reason", "end_turn")
    usage = result.get("usage", {"input_tokens": 0, "output_tokens": 0})
    yield f"event: message_delta\ndata: {json.dumps({'type':'message_delta','delta':{'stop_reason':stop_reason,'stop_sequence':None},'usage':usage})}\n\n"
    yield f"event: message_stop\ndata: {json.dumps({'type':'message_stop'})}\n\n"


# ── Routes ──────────────────────────────────────────────────────────────────
@app.post("/v1/chat/completions")
async def chat_completions(req: ChatRequest):
    """OpenAI 兼容接口。"""
    return await _handle_chat(req, fmt="openai")


@app.post("/v1/messages")
async def anthropic_messages(req: Request):
    """Anthropic 兼容接口（供 cc-switch Claude Code 使用）。支持流式和非流式、多模态。"""
    body = await req.json()

    # ── 工具调用检测（优先级最高）──────────────────────────────────────────
    if body.get("tools"):
        is_stream = body.get("stream", False)
        if is_stream:
            return StreamingResponse(
                _tool_call_stream(body),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
            )
        else:
            result = await _tool_call_forward(body)
            return JSONResponse(result)

    has_image = False
    raw_messages = body.get("messages", [])

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

    # 含图片时：直接转发给支持视觉的后端（Claude）
    if has_image:
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
            _anthropic_stream(chat_req, req_model),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
        )
    return await _handle_chat(chat_req, fmt="anthropic", request_model=req_model)


async def _anthropic_stream_passthrough(body: dict, model: str):
    """含图片时：转发给视觉模型，流式返回。"""
    import httpx
    query_text = ""
    for m in body.get("messages", []):
        c = m.get("content", "")
        if isinstance(c, list):
            query_text = " ".join(b.get("text", "") for b in c if b.get("type") == "text")
        elif isinstance(c, str):
            query_text = c

    # 视觉模型不可用时，返回提示
    content = f"[图片分析] 收到包含图片的请求。当前视觉模型暂未接入，请用文字描述图片内容后重新提问。\n\n你的文字描述：{query_text}" if query_text else "[图片分析] 收到图片请求，请附带文字描述以便分析。"

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


async def _anthropic_stream(req: ChatRequest, model: str):
    """Anthropic SSE 流式响应。"""
    query = extract_query(req.messages)
    t0 = time.time()

    # 快速直答：元问题/问候，不调用后端（0ms）
    instant = _try_instant_reply(query)
    if instant:
        content = instant
        backend_used = "instant"
        intent_used = "instant"
    else:
        intent_used = smart_router.analyze(query)
        use_orch = needs_orchestration(query, intent_used)
        if use_orch:
            result = await asyncio.to_thread(orchestrate, query)
        else:
            result = await asyncio.to_thread(smart_router.route, query)
        content = result.get("answer", "")
        backend_used = result.get("backend", "unknown")

    duration_ms = int((time.time() - t0) * 1000)
    _record_request(query, backend_used, intent_used, duration_ms, True)

    # 在回答末尾标注后端来源
    content += f"\n\n---\n`[red V1flash → {backend_used}]`"
    msg_id = f"msg_{uuid.uuid4().hex[:24]}"

    # message_start
    yield f"event: message_start\ndata: {json.dumps({'type':'message_start','message':{'id':msg_id,'type':'message','role':'assistant','model':model,'content':[],'stop_reason':None,'stop_sequence':None,'usage':{'input_tokens':10,'output_tokens':0}}})}\n\n"

    # content_block_start
    yield f"event: content_block_start\ndata: {json.dumps({'type':'content_block_start','index':0,'content_block':{'type':'text','text':''}})}\n\n"

    # content_block_delta - 分块发送
    chunk_size = 20
    for i in range(0, len(content), chunk_size):
        chunk = content[i:i+chunk_size]
        yield f"event: content_block_delta\ndata: {json.dumps({'type':'content_block_delta','index':0,'delta':{'type':'text_delta','text':chunk}}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.01)

    # content_block_stop
    yield f"event: content_block_stop\ndata: {json.dumps({'type':'content_block_stop','index':0})}\n\n"

    # message_delta
    yield f"event: message_delta\ndata: {json.dumps({'type':'message_delta','delta':{'stop_reason':'end_turn','stop_sequence':None},'usage':{'output_tokens':len(content)//4}})}\n\n"

    # message_stop
    yield f"event: message_stop\ndata: {json.dumps({'type':'message_stop'})}\n\n"

    # 记录日志
    sys_prompt = extract_system_prompt(req.messages)
    if sys_prompt:
        try:
            _log_sys_prompt(sys_prompt)
        except Exception:
            pass
    try:
        if os.environ.get("DISTILL_LOG", "0") == "1":
            smart_router._log_to_distill_queue(query, content, intent_used, backend_used)
    except Exception:
        pass


async def _handle_chat(req: ChatRequest, fmt: str = "openai", request_model: str = None):
    query = extract_query(req.messages)
    if not query.strip():
        raise HTTPException(status_code=400, detail="Empty query")

    chat_id = make_chat_id()
    t0 = time.time()

    # 快速直答
    instant = _try_instant_reply(query)
    if instant:
        duration_ms = int((time.time() - t0) * 1000)
        _record_request(query, "instant", "instant", duration_ms, True)
        if fmt == "anthropic":
            return JSONResponse(build_anthropic_response(chat_id, instant, "instant", request_model or MODEL_ID))
        return JSONResponse(build_response(chat_id, instant, "instant", duration_ms))

    # 判断是否需要编排模式
    intent = smart_router.analyze(query)
    use_orchestration = needs_orchestration(query, intent)

    if req.stream:
        return StreamingResponse(
            _stream_response(chat_id, query, use_orchestration),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
        )

    # 非流式：直接调用
    if use_orchestration:
        result = await asyncio.to_thread(orchestrate, query)
    else:
        result = await asyncio.to_thread(smart_router.route, query)

    content = result.get("answer", "")
    backend = result.get("backend", "unknown")
    total_ms = result.get("total_ms", 0)
    duration_ms = int((time.time() - t0) * 1000)

    # 记录统计
    _record_request(query, backend, intent, duration_ms, True)

    # 记录用户问答到 distill_queue（DISTILL_LOG=1 时启用）
    try:
        if os.environ.get("DISTILL_LOG", "0") == "1":
            smart_router._log_to_distill_queue(query, content, intent, backend)
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


async def _stream_response(chat_id: str, query: str, use_orchestration: bool):
    """SSE 流式生成器：逐句输出。"""
    if use_orchestration:
        result = await asyncio.to_thread(orchestrate, query)
    else:
        result = await asyncio.to_thread(smart_router.route, query)

    content = result.get("answer", "")

    # 模拟流式：按句子分割输出
    sentences = _split_sentences(content)
    for sentence in sentences:
        yield build_stream_chunk(chat_id, sentence)
        await asyncio.sleep(0.02)

    # 结束标记
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


@app.get("/v1/models")
async def list_models():
    """返回模型列表，让 IDE 识别可用模型。"""
    return {
        "object": "list",
        "data": [
            {
                "id": MODEL_ID,
                "object": "model",
                "created": MODEL_CREATED,
                "owned_by": "red-v1flash",
                "permission": [],
                "root": MODEL_ID,
                "parent": None
            }
        ]
    }


@app.get("/health")
async def health():
    """健康检查端点。"""
    return {"status": "ok", "version": "2.0", "model": MODEL_ID}


@app.get("/v1/status")
async def router_status():
    """路由器状态：熔断器、后端列表、路由表。"""
    return {
        "circuit_breakers": smart_router.cb_status(),
        "backends": list(smart_router.BACKENDS.keys()),
        "route_table": smart_router.ROUTE,
        "public_model": smart_router.PUBLIC_MODEL_NAME
    }


# ── Admin API ──────────────────────────────────────────────────────────────────

@app.get("/admin/api/stats")
async def admin_stats():
    """返回实时统计数据。"""
    with _stats_lock:
        uptime = int(time.time() - _stats["start_time"])
        total = _stats["total_requests"]
        backend_calls = dict(_stats["backend_calls"])
        avg_ms = 0
        if total > 0:
            total_ms_all = sum(b["total_ms"] for b in backend_calls.values())
            avg_ms = int(total_ms_all / total)
        return {
            "total_requests": total,
            "uptime_seconds": uptime,
            "avg_response_ms": avg_ms,
            "backend_calls": backend_calls,
            "intent_distribution": dict(_stats["intent_distribution"]),
        }


@app.get("/admin/api/backends")
async def admin_backends():
    """返回后端列表和状态。"""
    cb = smart_router.cb_status()
    backends = []
    for name, cfg in smart_router.BACKENDS.items():
        enabled = _backend_enabled.get(name, True)
        status_info = cb.get(name, {})
        # 自动检测供应商
        url = cfg.get("url", "")
        vendor = "未知"
        if "longcat" in url: vendor = "LongCat"
        elif "nvidia" in url or "integrate.api.nvidia" in url: vendor = "英伟达 NVIDIA"
        elif "openrouter" in url: vendor = "OpenRouter (免费)"
        elif "deepseek" in url: vendor = "DeepSeek"
        elif "chinamobile" in url: vendor = "中国移动"
        elif "right.codes" in url: vendor = "Claude (付费)"
        elif "localhost" in url or "127.0.0.1" in url: vendor = "本地模型"
        backends.append({
            "name": name,
            "vendor": vendor,
            "url": url,
            "model": cfg.get("model", ""),
            "fmt": cfg.get("fmt", ""),
            "enabled": enabled,
            "state": status_info.get("state", "closed"),
            "total_calls": status_info.get("total_calls", 0),
            "error_rate": status_info.get("error_rate", "0.0%"),
        })
    return backends


@app.post("/admin/api/backends")
async def admin_add_backend(req: Request):
    """添加新后端。"""
    body = await req.json()
    name = body.get("name", "").strip()
    url = body.get("url", "").strip()
    key = body.get("key", "").strip()
    model = body.get("model", name)
    fmt = body.get("fmt", "openai")
    if not name or not url:
        raise HTTPException(400, "name and url required")
    if name in smart_router.BACKENDS:
        raise HTTPException(409, f"backend '{name}' already exists")
    smart_router.BACKENDS[name] = {
        "url": url, "key": key, "model": model, "fmt": fmt
    }
    _backend_enabled[name] = True
    return {"ok": True, "message": f"backend '{name}' added"}


@app.delete("/admin/api/backends/{name}")
async def admin_delete_backend(name: str):
    """删除后端。"""
    if name not in smart_router.BACKENDS:
        raise HTTPException(404, f"backend '{name}' not found")
    del smart_router.BACKENDS[name]
    _backend_enabled.pop(name, None)
    return {"ok": True, "message": f"backend '{name}' deleted"}


@app.post("/admin/api/backends/{name}/toggle")
async def admin_toggle_backend(name: str):
    """启用/禁用后端。"""
    if name not in smart_router.BACKENDS:
        raise HTTPException(404, f"backend '{name}' not found")
    current = _backend_enabled.get(name, True)
    _backend_enabled[name] = not current
    return {"ok": True, "enabled": not current}


@app.get("/admin/api/logs")
async def admin_logs():
    """返回最近请求日志。"""
    with _stats_lock:
        return list(reversed(_stats["recent_logs"][-10:]))


@app.get("/admin/api/rules")
async def admin_get_rules():
    """返回预设直答规则。"""
    rules = []
    for i, (pattern, reply) in enumerate(_INSTANT_REPLIES):
        rules.append({"id": i, "pattern": pattern.pattern, "reply": reply})
    return rules


@app.post("/admin/api/rules")
async def admin_add_rule(req: Request):
    """添加预设直答规则。"""
    body = await req.json()
    pattern_str = body.get("pattern", "").strip()
    reply = body.get("reply", "").strip()
    if not pattern_str or not reply:
        raise HTTPException(400, "pattern and reply required")
    try:
        compiled = _re.compile(pattern_str, _re.IGNORECASE)
    except _re.error as e:
        raise HTTPException(400, f"invalid regex: {e}")
    _INSTANT_REPLIES.append((compiled, reply))
    return {"ok": True, "id": len(_INSTANT_REPLIES) - 1}


@app.delete("/admin/api/rules/{rule_id}")
async def admin_delete_rule(rule_id: int):
    """删除预设直答规则。"""
    if rule_id < 0 or rule_id >= len(_INSTANT_REPLIES):
        raise HTTPException(404, "rule not found")
    _INSTANT_REPLIES.pop(rule_id)
    return {"ok": True}


# ── Admin HTML ─────────────────────────────────────────────────────────────────

ADMIN_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>red V1flash - 管理后台</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#1a1a2e;color:#e0e0e0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;padding:20px}
h1{color:#00d4ff;margin-bottom:20px;font-size:1.6em}
h2{color:#00d4ff;margin-bottom:12px;font-size:1.1em;border-bottom:1px solid #2a2a4e;padding-bottom:6px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px;margin-bottom:24px}
.card{background:#16213e;border-radius:10px;padding:18px;border:1px solid #2a2a4e}
.stat-num{font-size:2em;font-weight:700;color:#00d4ff}
.stat-label{font-size:0.85em;color:#888;margin-top:4px}
table{width:100%;border-collapse:collapse;font-size:0.85em}
th,td{padding:8px 10px;text-align:left;border-bottom:1px solid #2a2a4e}
th{color:#00d4ff;font-weight:600}
tr:hover{background:#1f2b47}
.badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:0.75em;font-weight:600}
.badge-ok{background:#0d4d2e;color:#4caf50}
.badge-err{background:#4d0d0d;color:#f44336}
.badge-off{background:#3d3d3d;color:#999}
button{background:#00d4ff;color:#1a1a2e;border:none;padding:6px 14px;border-radius:5px;cursor:pointer;font-size:0.8em;font-weight:600}
button:hover{background:#00b8d4}
button.danger{background:#f44336;color:#fff}
button.danger:hover{background:#d32f2f}
input,select{background:#0f1a30;border:1px solid #2a2a4e;color:#e0e0e0;padding:6px 10px;border-radius:5px;font-size:0.85em}
input:focus,select:focus{outline:none;border-color:#00d4ff}
.form-row{display:flex;gap:8px;margin-top:10px;flex-wrap:wrap;align-items:center}
.form-row input{flex:1;min-width:120px}
.log-time{color:#888;font-size:0.8em}
.log-backend{color:#00d4ff}
.log-query{color:#ccc;max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.tabs{display:flex;gap:4px;margin-bottom:16px}
.tab{padding:8px 18px;background:#16213e;border:1px solid #2a2a4e;border-radius:6px 6px 0 0;cursor:pointer;color:#888}
.tab.active{background:#1f2b47;color:#00d4ff;border-bottom-color:#1f2b47}
.panel{display:none}
.panel.active{display:block}
.refresh-info{font-size:0.75em;color:#555;margin-left:12px}
</style>
</head>"""

ADMIN_BODY = """<body>
<h1>red V1flash 管理后台<span class="refresh-info" id="refresh-info">每5秒自动刷新</span></h1>
<div class="tabs">
  <div class="tab active" onclick="switchTab('stats')">实时指标</div>
  <div class="tab" onclick="switchTab('backends')">后端管理</div>
  <div class="tab" onclick="switchTab('rules')">直答规则</div>
</div>

<div id="panel-stats" class="panel active">
  <div class="grid">
    <div class="card"><div class="stat-num" id="s-total">0</div><div class="stat-label">总请求数</div></div>
    <div class="card"><div class="stat-num" id="s-avg-ms">0ms</div><div class="stat-label">平均响应时间</div></div>
    <div class="card"><div class="stat-num" id="s-uptime">0s</div><div class="stat-label">运行时间</div></div>
    <div class="card"><div class="stat-num" id="s-backends">0</div><div class="stat-label">活跃后端</div></div>
  </div>
  <div class="grid">
    <div class="card"><h2>后端调用统计</h2><table><thead><tr><th>后端</th><th>调用</th><th>成功率</th><th>平均ms</th></tr></thead><tbody id="t-backends"></tbody></table></div>
    <div class="card"><h2>意图分布</h2><table><thead><tr><th>意图</th><th>次数</th><th>占比</th></tr></thead><tbody id="t-intents"></tbody></table></div>
  </div>
  <div class="card" style="margin-top:16px"><h2>最近请求日志</h2><table><thead><tr><th>时间</th><th>查询</th><th>后端</th><th>意图</th><th>耗时</th><th>状态</th></tr></thead><tbody id="t-logs"></tbody></table></div>
</div>

<div id="panel-backends" class="panel">
  <div class="card" style="margin-bottom:16px">
    <h2>添加新后端</h2>
    <div class="form-row">
      <input id="nb-name" placeholder="名称 (如 my_backend)">
      <input id="nb-url" placeholder="API URL">
      <input id="nb-key" placeholder="API Key (可选)">
      <input id="nb-model" placeholder="模型名 (可选)">
      <select id="nb-fmt"><option value="openai">OpenAI</option><option value="anthropic">Anthropic</option></select>
      <button onclick="addBackend()">添加</button>
    </div>
  </div>
  <div class="card"><h2>后端列表</h2><table><thead><tr><th>名称</th><th>供应商</th><th>模型</th><th>URL</th><th>状态</th><th>熔断</th><th>调用</th><th>错误率</th><th>操作</th></tr></thead><tbody id="t-be-list"></tbody></table></div>
</div>

<div id="panel-rules" class="panel">
  <div class="card" style="margin-bottom:16px">
    <h2>添加直答规则</h2>
    <div class="form-row">
      <input id="nr-pattern" placeholder="正则表达式" style="flex:2">
      <input id="nr-reply" placeholder="回复内容" style="flex:3">
      <button onclick="addRule()">添加</button>
    </div>
  </div>
  <div class="card"><h2>当前规则</h2><table><thead><tr><th>#</th><th>匹配模式</th><th>回复</th><th>操作</th></tr></thead><tbody id="t-rules"></tbody></table></div>
</div>"""

ADMIN_JS = """<script>
function switchTab(name){
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
  event.target.classList.add('active');
  document.getElementById('panel-'+name).classList.add('active');
}
function fmtUptime(s){
  if(s<60)return s+'s';
  if(s<3600)return Math.floor(s/60)+'m '+s%60+'s';
  let h=Math.floor(s/3600),m=Math.floor((s%3600)/60);
  return h+'h '+m+'m';
}
async function loadStats(){
  try{
    let r=await fetch('/admin/api/stats');let d=await r.json();
    document.getElementById('s-total').textContent=d.total_requests;
    document.getElementById('s-avg-ms').textContent=d.avg_response_ms+'ms';
    document.getElementById('s-uptime').textContent=fmtUptime(d.uptime_seconds);
    document.getElementById('s-backends').textContent=Object.keys(d.backend_calls).length;
    let tb=document.getElementById('t-backends');tb.innerHTML='';
    for(let[name,info]of Object.entries(d.backend_calls)){
      let rate=info.count>0?Math.round(info.success/info.count*100):0;
      let avg=info.count>0?Math.round(info.total_ms/info.count):0;
      tb.innerHTML+=`<tr><td>${name}</td><td>${info.count}</td><td><span class="badge ${rate>90?'badge-ok':'badge-err'}">${rate}%</span></td><td>${avg}</td></tr>`;
    }
    let ti=document.getElementById('t-intents');ti.innerHTML='';
    let total=Object.values(d.intent_distribution).reduce((a,b)=>a+b,0)||1;
    let sorted=Object.entries(d.intent_distribution).sort((a,b)=>b[1]-a[1]);
    for(let[intent,count]of sorted){
      ti.innerHTML+=`<tr><td>${intent}</td><td>${count}</td><td>${Math.round(count/total*100)}%</td></tr>`;
    }
  }catch(e){console.error('stats error',e)}
}
async function loadLogs(){
  try{
    let r=await fetch('/admin/api/logs');let d=await r.json();
    let tl=document.getElementById('t-logs');tl.innerHTML='';
    for(let log of d){
      let cls=log.success?'badge-ok':'badge-err';
      tl.innerHTML+=`<tr><td class="log-time">${log.time}</td><td class="log-query" title="${log.query}">${log.query}</td><td class="log-backend">${log.backend}</td><td>${log.intent}</td><td>${log.ms}ms</td><td><span class="badge ${cls}">${log.success?'OK':'ERR'}</span></td></tr>`;
    }
  }catch(e){console.error('logs error',e)}
}
async function loadBackends(){
  try{
    let r=await fetch('/admin/api/backends');let d=await r.json();
    let tb=document.getElementById('t-be-list');tb.innerHTML='';
    for(let b of d){
      let stCls=b.enabled?'badge-ok':'badge-off';
      let stTxt=b.enabled?'启用':'禁用';
      let cbCls=b.state==='open'?'badge-err':'badge-ok';
      tb.innerHTML+=`<tr><td>${b.name}</td><td>${b.vendor||''}</td><td>${b.model}</td><td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;font-size:11px">${b.url}</td><td><span class="badge ${stCls}">${stTxt}</span></td><td><span class="badge ${cbCls}">${b.state||'closed'}</span></td><td>${b.total_calls}</td><td>${b.error_rate}</td><td><button onclick="toggleBackend('${b.name}')">${b.enabled?'禁用':'启用'}</button> <button class="danger" onclick="deleteBackend('${b.name}')">删除</button></td></tr>`;
    }
  }catch(e){console.error('backends error',e)}
}
async function loadRules(){
  try{
    let r=await fetch('/admin/api/rules');let d=await r.json();
    let tb=document.getElementById('t-rules');tb.innerHTML='';
    for(let rule of d){
      tb.innerHTML+=`<tr><td>${rule.id}</td><td style="max-width:300px;overflow:hidden;text-overflow:ellipsis">${rule.pattern}</td><td style="max-width:400px;overflow:hidden;text-overflow:ellipsis">${rule.reply}</td><td><button class="danger" onclick="deleteRule(${rule.id})">删除</button></td></tr>`;
    }
  }catch(e){console.error('rules error',e)}
}
async function addBackend(){
  let name=document.getElementById('nb-name').value.trim();
  let url=document.getElementById('nb-url').value.trim();
  let key=document.getElementById('nb-key').value.trim();
  let model=document.getElementById('nb-model').value.trim();
  let fmt=document.getElementById('nb-fmt').value;
  if(!name||!url){alert('名称和URL必填');return}
  let r=await fetch('/admin/api/backends',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,url,key,model:model||name,fmt})});
  if(r.ok){document.getElementById('nb-name').value='';document.getElementById('nb-url').value='';document.getElementById('nb-key').value='';document.getElementById('nb-model').value='';loadBackends()}
  else{let e=await r.json();alert(e.detail||'添加失败')}
}
async function deleteBackend(name){
  if(!confirm('确定删除后端 '+name+' ?'))return;
  await fetch('/admin/api/backends/'+name,{method:'DELETE'});loadBackends();
}
async function toggleBackend(name){
  await fetch('/admin/api/backends/'+name+'/toggle',{method:'POST'});loadBackends();
}
async function addRule(){
  let pattern=document.getElementById('nr-pattern').value.trim();
  let reply=document.getElementById('nr-reply').value.trim();
  if(!pattern||!reply){alert('模式和回复必填');return}
  let r=await fetch('/admin/api/rules',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pattern,reply})});
  if(r.ok){document.getElementById('nr-pattern').value='';document.getElementById('nr-reply').value='';loadRules()}
  else{let e=await r.json();alert(e.detail||'添加失败')}
}
async function deleteRule(id){
  if(!confirm('确定删除规则 #'+id+' ?'))return;
  await fetch('/admin/api/rules/'+id,{method:'DELETE'});loadRules();
}
function refreshAll(){loadStats();loadLogs();loadBackends();loadRules()}
refreshAll();
setInterval(refreshAll,5000);
</script>
</body>
</html>"""


@app.get("/admin", response_class=HTMLResponse)
async def admin_page():
    """管理后台 Web UI。"""
    return HTMLResponse(ADMIN_HTML + ADMIN_BODY + ADMIN_JS)


# ── Startup ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
