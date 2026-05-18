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


def extract_query(messages: list[Message]) -> str:
    """从 messages 列表提取最后一条 user 消息作为 query。"""
    for msg in reversed(messages):
        if msg.role == "user":
            return msg.content
    return messages[-1].content if messages else ""


# ── Routes ──────────────────────────────────────────────────────────────────
@app.post("/v1/chat/completions")
async def chat_completions(req: ChatRequest):
    """主接口：兼容 OpenAI ChatCompletion 格式。"""
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
