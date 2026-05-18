"""server.py — red V1flash OpenAI 兼容接口层
让 Cursor、Claude Code、VS Code Copilot 等 AI IDE 直接接入。
支持流式/非流式 ChatCompletion，兼容 OpenAI API 格式。
"""
import sys, os, json, time, uuid, asyncio
from typing import Optional
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
import uvicorn

import smart_router
from orchestrate import orchestrate, needs_orchestration

# ── App ─────────────────────────────────────────────────────────────────────
app = FastAPI(title="red V1flash", version="2.0",
              description="CNC/Embedded AI Router — OpenAI Compatible API")

MODEL_ID = "red-v1flash"
MODEL_CREATED = int(time.time())


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
    (_re.compile(r'你是什么|什么模型|who are you|what model|what are you|哪个模型', _re.IGNORECASE),
     "我是 red V1flash，由深圳市动力巢科技有限公司训练的智能路由编排模型。我能自动分析你的问题，从 22 个 AI 后端中选择最合适的模型来回答，实现 1+N 远大于 N 的效果。"),
    (_re.compile(r'^(hi|hello|hey|你好|嗨)[\s!！.。?？]*$', _re.IGNORECASE),
     "你好！我是 red V1flash，深圳市动力巢科技有限公司的智能路由编排模型。直接提问即可，我会自动选择最佳模型为你解答。"),
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


# ── Routes ──────────────────────────────────────────────────────────────────
@app.post("/v1/chat/completions")
async def chat_completions(req: ChatRequest):
    """OpenAI 兼容接口。"""
    return await _handle_chat(req, fmt="openai")


@app.post("/v1/messages")
async def anthropic_messages(req: Request):
    """Anthropic 兼容接口（供 cc-switch Claude Code 使用）。支持流式和非流式。"""
    body = await req.json()
    messages = [Message(role=m["role"], content=m.get("content", ""))
                for m in body.get("messages", []) if m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str)]
    if body.get("system"):
        if isinstance(body["system"], str):
            messages.insert(0, Message(role="system", content=body["system"]))
        elif isinstance(body["system"], list):
            txt = " ".join(b.get("text", "") for b in body["system"] if b.get("type") == "text")
            if txt:
                messages.insert(0, Message(role="system", content=txt))

    req_model = body.get("model", MODEL_ID)
    is_stream = body.get("stream", False)

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


async def _anthropic_stream(req: ChatRequest, model: str):
    """Anthropic SSE 流式响应。"""
    query = extract_query(req.messages)

    # 快速直答：元问题/问候，不调用后端（0ms）
    instant = _try_instant_reply(query)
    if instant:
        content = instant
    else:
        intent = smart_router.analyze(query)
        use_orch = needs_orchestration(query, intent)
        if use_orch:
            result = await asyncio.to_thread(orchestrate, query)
        else:
            result = await asyncio.to_thread(smart_router.route, query)
        content = result.get("answer", "")
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
            smart_router._log_to_distill_queue(query, content, intent, result.get("backend", "unknown"))
    except Exception:
        pass


async def _handle_chat(req: ChatRequest, fmt: str = "openai", request_model: str = None):
    query = extract_query(req.messages)
    if not query.strip():
        raise HTTPException(status_code=400, detail="Empty query")

    chat_id = make_chat_id()

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


# ── Startup ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
