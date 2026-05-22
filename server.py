"""server.py — LiMa（力码）OpenAI 兼容接口层
让 Cursor、Claude Code、VS Code Copilot 等 AI IDE 直接接入。
支持流式/非流式 ChatCompletion，兼容 OpenAI API 格式。
"""
import sys, os, json, time, uuid, asyncio, threading, functools
from typing import Optional, Union
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Request, HTTPException, Depends, Header
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse
from pydantic import BaseModel, Field
import uvicorn

import smart_router
from orchestrate import orchestrate, needs_orchestration


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

# ── V3 路由引擎（灰度切换） ──────────────────────────────────────────────────
USE_V3 = os.environ.get("LIMA_V3", "1") == "1"
if USE_V3:
    import routing_engine
    import http_caller
    import health_tracker
    import streaming as streaming_mod

    def _v3_route(query, messages, system_prompt="", ide="", max_tokens=4096, **_kw):
        """V3 路由适配器：返回与 smart_router.route() 兼容的 dict。"""
        def _call_fn(backend, msgs, mt):
            return http_caller.call_api(backend, msgs, mt,
                                        system_prompt=system_prompt, ide=ide)
        result = routing_engine.route(
            query, messages, fmt="openai", ide_source=ide,
            system_prompt=system_prompt, max_tokens=max_tokens,
            call_fn=_call_fn)
        return {"answer": result.answer, "backend": result.backend,
                "total_ms": result.ms, "fallback_used": result.fallback_used}

    def _v3_predict(query):
        """V3 快速预测：根据场景选择后端池。"""
        import health_tracker as ht
        hmap = ht.get_health_map()
        try:
            from routing_engine import classify_scenario
            scenario = classify_scenario(query, [], request_type="")
            if scenario == "coding":
                import code_orchestrator
                pool = code_orchestrator.backend_reputation.sort_by_reputation(
                    code_orchestrator.POOLS["coder"])
                if pool:
                    return pool[0]
            else:
                chat_only = ["deepseek_free", "zhipu_flash", "cf_llama70b",
                             "groq_llama70b", "longcat_lite", "longcat_chat"]
                for b in chat_only:
                    if not ht.is_cooled_down(b):
                        return b
                return "groq_llama70b"
        except Exception:
            pass
        backends = routing_engine.select("chat", hmap, scenario="chat")
        return backends[0] if backends else "longcat_chat"

    def _v3_select(query, system_prompt, ide, messages):
        """V3 完整路由选择：根据场景选后端。"""
        import health_tracker as ht
        hmap = ht.get_health_map()
        is_ide = bool(ide and ide not in ("unknown", ""))
        try:
            from routing_engine import classify_scenario
            scenario = classify_scenario(query, messages,
                                         ide_source=ide if is_ide else "",
                                         request_type="ide" if is_ide else "chat")
            if scenario == "coding":
                import code_orchestrator
                pool = code_orchestrator.backend_reputation.sort_by_reputation(
                    code_orchestrator.POOLS["coder"])
                if pool:
                    return (pool[0], messages)
            else:
                chat_only = ["deepseek_free", "zhipu_flash", "cf_llama70b",
                             "groq_llama70b", "longcat_lite", "longcat_chat"]
                for b in chat_only:
                    if not ht.is_cooled_down(b):
                        return (b, messages)
                return ("groq_llama70b", messages)
        except Exception:
            pass
        backends = routing_engine.select("chat", hmap, scenario="chat")
        return (backends[0] if backends else "longcat_chat", messages)

# 非真流式后端（代理/逆向），强制走非流式保证身份清洗完整
_FAKE_STREAM_BACKENDS = {'deepseek_free'}

def _v3_call_stream(backend, messages, max_tokens, ide):
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
            else:
                sys_prompt = "Answer the question directly in plain text. Do not generate code, functions, or programming examples unless the user explicitly asks for code."
    except Exception:
        pass

    if backend in _FAKE_STREAM_BACKENDS:
        result = http_caller.call_api(
            backend, messages, max_tokens, system_prompt=sys_prompt, ide=ide)
        return _fake_stream(result)
    return http_caller.call_api_stream(
        backend, messages, max_tokens, system_prompt=sys_prompt, ide=ide)

def _v3_call_api(backend, messages, max_tokens, ide):
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
    except Exception:
        pass
    return http_caller.call_api(
        backend, messages, max_tokens, system_prompt=sys_prompt, ide=ide)

def _fake_stream(text: str, chunk_size: int = 30):
    """将完整文本拆为 chunk 模拟流式输出。已清洗的文本直接拆。"""
    for i in range(0, len(text), chunk_size):
        yield text[i:i+chunk_size]

# ── App ─────────────────────────────────────────────────────────────────────
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(application):
    """FastAPI lifespan: 启动/关闭时执行。"""
    if USE_V3:
        import probe_loop
        probe_loop.start(probe_fn=http_caller.probe)
    yield
    if USE_V3:
        import probe_loop
        probe_loop.stop()

app = FastAPI(title="LiMa", version="1.3",
              description="LiMa（力码）— 智能编程助手 API，OpenAI 兼容",
              lifespan=lifespan)

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

# ── Fallback 日志（供自动训练闭环使用）────────────────────────────────────────
FALLBACK_LOG = "D:/GIT/data/fallback_log.jsonl"


def _record_fallback(query, original_backend, fallback_backend, intent, ide):
    """记录 fallback 事件到日志文件，供 auto_retrain 自动训练使用。"""
    try:
        os.makedirs(os.path.dirname(FALLBACK_LOG), exist_ok=True)
        entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "query": query[:300],
            "original_backend": original_backend,
            "fallback_backend": fallback_backend,
            "intent": intent,
            "ide": ide,
        }
        with open(FALLBACK_LOG, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    except Exception:
        pass

# ── Fallback 架构 ─────────────────────────────────────────────────────────────
# 后端层级映射
BACKEND_TIERS = {
    "L1_free": ["longcat_lite", "longcat_chat", "longcat", "longcat_thinking", "longcat_omni", "chinamobile"],
    "L2_nvidia": ["nvidia_qwen_coder", "nvidia_nemotron", "nvidia_phi4", "nvidia_llama4", "nvidia_llama70b", "nvidia_mistral"],
    "L2_openrouter": ["or_deepseek_r1", "or_qwen3_coder", "or_llama70b", "or_nemotron", "or_qwen3_80b"],
    "L3_paid": [],
}


def _get_same_tier_backends(current_backend: str) -> list:
    """获取同层级的其他后端（排除当前的）。"""
    for tier, backends in BACKEND_TIERS.items():
        if current_backend in backends:
            return [b for b in backends if b != current_backend]
    return []


def _get_upgrade_chain(current_backend: str) -> list:
    """获取升级链：当前层级之上的所有后端。"""
    tiers = list(BACKEND_TIERS.keys())
    current_tier = None
    for tier, backends in BACKEND_TIERS.items():
        if current_backend in backends:
            current_tier = tier
            break
    if not current_tier:
        return ["longcat_chat"]  # 默认 fallback
    tier_idx = tiers.index(current_tier)
    upgrade_backends = []
    for tier in tiers[tier_idx + 1:]:
        upgrade_backends.extend(BACKEND_TIERS[tier][:2])  # 每层取前2个
    return upgrade_backends


def _default_route(query: str, ide: str = "unknown") -> str:
    """当路由模型输出无效时，用简单规则选后端。"""
    query_len = len(query)
    # 短问题用快速后端
    if query_len < 50:
        return "longcat_lite"
    # 代码相关关键词
    code_keywords = ["代码", "code", "函数", "function", "bug", "error", "def ", "class ", "import "]
    if any(kw in query.lower() for kw in code_keywords):
        return "nvidia_qwen_coder"
    # 长问题用通用后端
    if query_len > 200:
        return "longcat"
    # 默认
    return "longcat_chat"


def _quality_check(response_text: str, complexity: float, backend: str) -> bool:
    """检查回答质量，返回 False 表示需要重试。"""
    if not response_text:
        return False
    if len(response_text) < 30 and complexity > 0.3:
        return False
    if response_text.startswith("[ERR]"):
        return False
    if http_caller._is_backend_error(response_text):
        return False
    uncertain_phrases = ["I cannot", "我无法", "抱歉，我不能"]
    if any(phrase in response_text for phrase in uncertain_phrases):
        if complexity < 0.5:
            return False
    return True


def _honest_failure_response(chat_id: str, fmt: str = "openai", request_model: str = None) -> dict:
    """所有后端都失败时的诚实回答。"""
    content = "当前所有服务暂时不可用，请稍后重试。如果问题持续，请联系管理员。"
    if fmt == "anthropic":
        return build_anthropic_response(chat_id, content, "fallback_exhausted", request_model or MODEL_ID)
    return build_response(chat_id, content, "fallback_exhausted", 0)


async def _try_backend(backend_name: str, query: str, max_tokens: int = 1024) -> dict | None:
    """尝试调用一个后端，失败返回 None。返回 smart_router.route() 兼容的 dict。"""
    if backend_name not in smart_router.BACKENDS:
        return None
    if not _backend_enabled.get(backend_name, True):
        return None
    if not smart_router.cb_allow(backend_name):
        return None
    try:
        msgs = [{"role": "user", "content": query}]
        result = await asyncio.wait_for(
            asyncio.to_thread(smart_router.call_api, backend_name, msgs, max_tokens),
            timeout=35.0
        )
        if result is None or (isinstance(result, str) and (result.startswith("[ERR]") or "暂时不可用" in result)):
            smart_router.cb_record(backend_name, False)
            return None
        return {"answer": result, "backend": backend_name, "total_ms": 0}
    except asyncio.TimeoutError:
        smart_router.cb_record(backend_name, False)
        return None
    except Exception:
        smart_router.cb_record(backend_name, False)
        return None


@functools.lru_cache(maxsize=256)
def _get_ip_location(ip: str) -> str:
    """查询 IP 地理位置（缓存结果）。"""
    if ip in ("127.0.0.1", "localhost", "::1", ""):
        return "本地"
    import re
    if not re.match(r'^[\d.:a-fA-F]+$', ip):
        return "未知"
    try:
        import urllib.request
        resp = urllib.request.urlopen(f"http://ip-api.com/json/{ip}?fields=country,city&lang=zh-CN", timeout=0.5)
        data = json.loads(resp.read().decode())
        return f"{data.get('country', '')} {data.get('city', '')}"
    except Exception:
        return "未知"


def _detect_ide(messages: list) -> str:
    """从消息中检测 IDE 来源。"""
    for msg in messages:
        content = msg.get("content", "") if isinstance(msg, dict) else ""
        if isinstance(content, str):
            if "Claude Code" in content or "claude-code" in content:
                return "Claude Code"
            if "Cursor" in content or "You are Cursor" in content:
                return "Cursor"
            if "GitHub Copilot" in content:
                return "GitHub Copilot"
            if "Windsurf" in content:
                return "Windsurf"
            if "Codex" in content:
                return "Codex"
            if "Continue" in content:
                return "Continue"
            if "Cline" in content:
                return "Cline"
    return "未知"


def _record_request(query: str, backend: str, intent: str, duration_ms: int, success: bool = True, client_ip: str = "", ide_source: str = "", sys_prompt_preview: str = ""):
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
            "ip": client_ip,
            "country": _get_ip_location(client_ip) if client_ip else "",
            "ide": ide_source,
            "sys_prompt": sys_prompt_preview[:100] if sys_prompt_preview else "",
        }
        _stats["recent_logs"].append(log_entry)
        if len(_stats["recent_logs"]) > 100:
            _stats["recent_logs"] = _stats["recent_logs"][-100:]


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
        "x_lima_meta": {"backend": backend, "total_ms": total_ms}
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


def messages_to_dicts(messages: list[Message]) -> list[dict]:
    """将 Pydantic Message 列表转为 dict 列表，用于传递完整上下文。"""
    return [{'role': m.role, 'content': m.content} for m in messages if m.role in ('user', 'assistant')]


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


# ── Vision (Photo-to-Answer) Mode Helper ─────────────────────────────────────
async def _vision_route(messages: list, max_tokens: int = 4096, ide: str = "unknown") -> dict | None:
    """Route vision requests to a multimodal backend. Returns result dict or None."""
    for backend_name in smart_router.VISION_BACKENDS:
        if backend_name not in smart_router.BACKENDS:
            continue
        if not smart_router.BACKENDS[backend_name].get('key'):
            continue
        if not smart_router.cb_allow(backend_name):
            continue
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(_call_vision_backend, backend_name, messages, max_tokens, ide),
                timeout=60.0
            )
            if result and not (isinstance(result, str) and (result.startswith("[ERR]") or "暂时不可用" in result)):
                return {"answer": result, "backend": backend_name}
        except (asyncio.TimeoutError, Exception) as e:
            if smart_router.DEBUG:
                print(f"[VISION] {backend_name} failed: {e}", file=sys.stderr)
            continue
    return None


def _call_vision_backend(backend_name: str, messages: list, max_tokens: int, ide: str) -> str | None:
    """Call a vision-capable backend with image content."""
    import urllib.request as _ur
    b = smart_router.BACKENDS[backend_name]
    fmt = b.get('fmt', 'openai')
    auth_style = b.get('auth', 'x-api-key')

    if fmt == 'anthropic':
        # Convert OpenAI vision format to Anthropic format
        anthropic_msgs = smart_router.convert_openai_vision_to_anthropic(messages)

        if b.get('no_system'):
            # For no_system backends (like longcat_omni): inject system prompt as first user message
            system_text_block = {"type": "text", "text": smart_router.VISION_SYSTEM_PROMPT}
            if anthropic_msgs and anthropic_msgs[0]["role"] == "user":
                anthropic_msgs[0]["content"].insert(0, system_text_block)
            else:
                anthropic_msgs.insert(0, {"role": "user", "content": [system_text_block]})
            body = {'model': b['model'], 'max_tokens': max_tokens, 'messages': anthropic_msgs}
        else:
            body = {'model': b['model'], 'max_tokens': max_tokens,
                    'system': smart_router.VISION_SYSTEM_PROMPT, 'messages': anthropic_msgs}

        p = json.dumps(body).encode()
        if auth_style == 'bearer':
            h = {'Content-Type': 'application/json',
                 'Authorization': f"Bearer {b['key']}",
                 'anthropic-version': '2023-06-01'}
        else:
            h = {'Content-Type': 'application/json',
                 'x-api-key': b['key'], 'anthropic-version': '2023-06-01'}
    else:
        # OpenAI format: pass messages through with vision system prompt
        openai_msgs = [{'role': 'system', 'content': smart_router.VISION_SYSTEM_PROMPT}] + messages
        body = {'model': b['model'], 'max_tokens': max_tokens, 'messages': openai_msgs}
        p = json.dumps(body).encode()
        h = {'Content-Type': 'application/json', 'Authorization': f"Bearer {b['key']}"}

    try:
        req = _ur.Request(b['url'], data=p, headers=h)
        _timeout = b.get('timeout', 60)
        with _ur.urlopen(req, timeout=_timeout) as resp:
            d = json.loads(resp.read().decode())
        if fmt == 'anthropic':
            answer = d['content'][0].get('text', '')
        else:
            answer = d['choices'][0]['message'].get('content', '')
        smart_router.cb_record(backend_name, True)
        return smart_router.clean_response(answer, backend_name)
    except Exception as e:
        if smart_router.DEBUG:
            print(f'[VISION] {backend_name} call error: {e}', file=sys.stderr)
        smart_router.cb_record(backend_name, False)
        return None


async def _stream_vision_response(chat_id: str, content: str):
    """Stream a vision response in OpenAI SSE format."""
    sentences = _split_sentences(content)
    for sentence in sentences:
        yield build_stream_chunk(chat_id, sentence)
        await asyncio.sleep(0.02)
    yield build_stream_chunk(chat_id, "", finish=True)
    yield "data: [DONE]\n\n"


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


# ── Tool Call Forwarding (DeepSeek R1 via OpenRouter) ─────────────────────────
import httpx as _httpx
import urllib.parse as _urllib_parse

TOOL_BACKEND_URL = "https://openrouter.ai/api/v1/chat/completions"
TOOL_BACKEND_MODEL = "deepseek/deepseek-v4-flash:free"
TOOL_BACKEND_KEY = os.environ.get("OPENROUTER_API_KEY", "")

ANTHROPIC_NATIVE_BACKENDS = ['longcat_chat', 'longcat', 'deepseek_free', 'longcat_lite', 'longcat_thinking', 'longcat_omni']

TOOL_TIER1_BACKENDS = [
    # Claude Code sends tools on most real requests. Keep this list short and
    # front-load low-latency OpenAI-compatible backends that handle tool_calls.
    'groq_gptoss_20b', 'cerebras_gptoss', 'groq_gptoss',
    'github_gpt4o_mini', 'github_gpt4o',
    'mistral_small', 'mistral_devstral', 'mistral_large',
    'scnet_large_ds_flash',
]


def _pick_tool_backend(tier: list):
    """从候选列表中按声明顺序选第一个健康后端（不用P2C，工具调用质量优先）。"""
    import health_tracker as _ht
    from backends import BACKENDS
    for n in tier:
        if BACKENDS.get(n, {}).get('key') and not _ht.is_cooled_down(n):
            return n
    return None


def _iter_tool_backends(tier: list):
    """Yield configured, non-cooled tool backends once per request."""
    import health_tracker as _ht
    from backends import BACKENDS
    for n in tier:
        if BACKENDS.get(n, {}).get('key') and not _ht.is_cooled_down(n):
            yield n


async def _anthropic_native_forward(body: dict) -> dict:
    """分层 tool 路由：第一梯队 OpenAI 格式(快) → 第二梯队 LongCat 原生(兜底)。"""
    return await asyncio.to_thread(_anthropic_native_forward_sync, body)


def _anthropic_native_forward_sync(body: dict) -> dict:
    """同步版本，在线程池中执行。使用 http_caller.call_raw() 确保代理正常工作。"""
    from http_caller import call_raw, BackendError
    from backends import BACKENDS

    # ── 估算 token 量，超大请求跳过 Tier 1 避免超时 ──
    body_size = len(json.dumps(body, ensure_ascii=False))
    skip_tier1 = body_size > 100000  # 100KB+, Claude Code ~30-40KB now passes

    # ── 第一梯队：OpenAI 格式后端（需格式转换）──
    openai_tools = _convert_tools_anthropic_to_openai(body.get("tools", []))
    openai_msgs = _convert_messages_anthropic_to_openai(body.get("messages", []))
    _inject_anthropic_context_preflight(openai_msgs, body)

    if not skip_tier1:
        for name in _iter_tool_backends(TOOL_TIER1_BACKENDS):
            b = BACKENDS[name]
            req_body = {"model": b["model"], "messages": openai_msgs,
                "tools": openai_tools, "max_tokens": body.get("max_tokens", 4096),
                "tool_choice": "auto"}
            if name.startswith("aliyun"):
                req_body["enable_thinking"] = False
            payload = json.dumps(req_body, ensure_ascii=False).encode()
            try:
                data = call_raw(name, payload)
                return _convert_response_openai_to_anthropic(data, b["model"])
            except BackendError:
                continue

    # ── 第二梯队：LongCat Anthropic 原生（兜底）──
    for _attempt in range(2):
        name = _pick_tool_backend(ANTHROPIC_NATIVE_BACKENDS)
        if not name:
            break
        b = BACKENDS[name]
        fwd = dict(body)
        fwd["model"] = b["model"]
        payload = json.dumps(fwd, ensure_ascii=False).encode()
        try:
            import urllib.request as _ur
            headers = {"Content-Type": "application/json",
                       "anthropic-version": "2023-06-01"}
            if b.get("auth") == "bearer":
                headers["Authorization"] = f"Bearer {b['key']}"
            else:
                headers["x-api-key"] = b["key"]
            req = _ur.Request(b["url"], data=payload, headers=headers)
            with _ur.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            import health_tracker as _ht
            _ht.record_success(name, 0)
            return data
        except Exception as e:
            import health_tracker as _ht
            code = getattr(e, 'code', None) or getattr(e, 'status', None) or 500
            _ht.record_failure(name, error_code=code)
            continue

    return {"type": "error", "error": {"type": "api_error",
            "message": "All tool backends exhausted"}}


async def _anthropic_native_stream(body: dict):
    """分层 tool 流式路由：第一梯队 OpenAI(快) → 第二梯队 LongCat(兜底)。"""
    from http_caller import call_raw, BackendError
    from backends import BACKENDS
    import health_tracker as _ht

    # ── 估算 token 量，超大请求跳过 Tier 1 避免超时 ──
    body_size = len(json.dumps(body, ensure_ascii=False))
    skip_tier1 = body_size > 100000  # 100KB+, Claude Code ~30-40KB now passes

    # ── 第一梯队：OpenAI 格式（非流式获取，模拟 Anthropic SSE 输出）──
    openai_tools = _convert_tools_anthropic_to_openai(body.get("tools", []))
    openai_msgs = _convert_messages_anthropic_to_openai(body.get("messages", []))
    _inject_anthropic_context_preflight(openai_msgs, body)

    if not skip_tier1:
        for name in _iter_tool_backends(TOOL_TIER1_BACKENDS):
            b = BACKENDS[name]
            req_body = {"model": b["model"], "messages": openai_msgs,
                "tools": openai_tools, "max_tokens": body.get("max_tokens", 4096),
                "tool_choice": "auto"}
            if name.startswith("aliyun"):
                req_body["enable_thinking"] = False
            payload = json.dumps(req_body, ensure_ascii=False).encode()
            try:
                data = await asyncio.to_thread(call_raw, name, payload)
                result = _convert_response_openai_to_anthropic(data, b["model"])
                for chunk in _simulate_anthropic_sse(result):
                    yield chunk
                return
            except BackendError as e:
                import health_tracker as _ht
                _ht.record_failure(name, error_code=e.status_code)
                continue
            except Exception as e:
                import health_tracker as _ht
                code = getattr(e, 'code', None) or getattr(e, 'status', None) or 500
                _ht.record_failure(name, error_code=code)
                continue

    # ── 第二梯队：LongCat Anthropic 原生流式 ──
    import urllib.request as _ur
    for _attempt in range(2):
        name = _pick_tool_backend(ANTHROPIC_NATIVE_BACKENDS)
        if not name:
            break
        b = BACKENDS[name]
        fwd = dict(body)
        fwd["model"] = b["model"]
        fwd["stream"] = True
        payload = json.dumps(fwd, ensure_ascii=False).encode()
        headers = {"Content-Type": "application/json",
                   "anthropic-version": "2023-06-01"}
        if b.get("auth") == "bearer":
            headers["Authorization"] = f"Bearer {b['key']}"
        else:
            headers["x-api-key"] = b["key"]
        try:
            req = _ur.Request(b["url"], data=payload, headers=headers)
            resp = _ur.urlopen(req, timeout=60)
            _ht.record_success(name, 0)
            buf = b''
            while True:
                chunk = resp.read(4096)
                if not chunk:
                    break
                buf += chunk
                while b'\n' in buf:
                    line, buf = buf.split(b'\n', 1)
                    decoded = line.decode('utf-8', errors='replace').strip()
                    if decoded:
                        yield decoded + '\n\n'
            if buf.strip():
                yield buf.decode('utf-8', errors='replace').strip() + '\n\n'
            resp.close()
            return
        except Exception:
            _ht.record_failure(name, error_code=None)
            continue
    yield 'event: error\ndata: {"type":"error","error":{"message":"All backends exhausted"}}\n\n'


def _simulate_anthropic_sse(result: dict):
    """把完整的 Anthropic 响应转为 SSE 事件流。"""
    msg_id = result.get("id", "msg_" + uuid.uuid4().hex[:12])
    model = result.get("model", "lima-1.3")
    yield f"event: message_start\ndata: {json.dumps({'type':'message_start','message':{'id':msg_id,'type':'message','role':'assistant','model':model,'content':[],'stop_reason':None,'usage':{'input_tokens':0,'output_tokens':0}}})}\n\n"
    for i, block in enumerate(result.get("content", [])):
        if block.get("type") == "text":
            yield f"event: content_block_start\ndata: {json.dumps({'type':'content_block_start','index':i,'content_block':{'type':'text','text':''}})}\n\n"
            text = block.get("text", "")
            for j in range(0, len(text), 40):
                yield f"event: content_block_delta\ndata: {json.dumps({'type':'content_block_delta','index':i,'delta':{'type':'text_delta','text':text[j:j+40]}}, ensure_ascii=False)}\n\n"
            yield f"event: content_block_stop\ndata: {json.dumps({'type':'content_block_stop','index':i})}\n\n"
        elif block.get("type") == "tool_use":
            yield f"event: content_block_start\ndata: {json.dumps({'type':'content_block_start','index':i,'content_block':{'type':'tool_use','id':block['id'],'name':block['name']}})}\n\n"
            yield f"event: content_block_delta\ndata: {json.dumps({'type':'content_block_delta','index':i,'delta':{'type':'input_json_delta','partial_json':json.dumps(block.get('input',{}), ensure_ascii=False)}})}\n\n"
            yield f"event: content_block_stop\ndata: {json.dumps({'type':'content_block_stop','index':i})}\n\n"
    stop_reason = result.get("stop_reason", "end_turn")
    yield f"event: message_delta\ndata: {json.dumps({'type':'message_delta','delta':{'stop_reason':stop_reason},'usage':result.get('usage',{})})}\n\n"
    yield f"event: message_stop\ndata: {json.dumps({'type':'message_stop'})}\n\n"


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


def _anthropic_system_text(body: dict) -> str:
    system = body.get("system", "")
    if isinstance(system, str):
        return system
    if isinstance(system, list):
        return " ".join(
            block.get("text", "") for block in system
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return ""


def _last_openai_user_text(messages: list) -> str:
    for message in reversed(messages):
        if message.get("role") == "user" and isinstance(message.get("content"), str):
            return message["content"]
    return ""


def _inject_anthropic_context_preflight(openai_msgs: list, body: dict) -> None:
    """Add request-local coding context to Claude Code tool requests."""
    sys_text = _anthropic_system_text(body)
    query = _last_openai_user_text(openai_msgs)
    try:
        from lima_context import build_context_digest
        digest = build_context_digest(
            query,
            openai_msgs,
            system_prompt=sys_text,
            ide_source="Claude Code",
        )
    except Exception:
        digest = ""

    combined = sys_text
    if digest:
        combined = f"{sys_text.rstrip()}\n\n{digest}".strip()
    if not combined:
        return
    if openai_msgs and openai_msgs[0].get("role") == "system":
        openai_msgs[0]["content"] = combined
    else:
        openai_msgs.insert(0, {"role": "system", "content": combined})


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


# ── Image Generation (Pollinations.ai) ────────────────────────────────────────
class ImageRequest(BaseModel):
    prompt: str
    model: str = "lima-image"
    size: str = Field(default="1024x1024", pattern=r"^\d{1,4}x\d{1,4}$")
    n: int = Field(default=1, ge=1, le=10)


def _build_pollinations_url(prompt: str, size: str = "1024x1024") -> str:
    """Build Pollinations.ai image URL from prompt and size."""
    parts = size.split("x")
    width = int(parts[0]) if len(parts) == 2 else 1024
    height = int(parts[1]) if len(parts) == 2 else 1024
    encoded_prompt = _urllib_parse.quote(prompt)
    return f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&nologo=true"


@app.post("/v1/images/generations")
async def image_generations(request: Request):
    """OpenAI-compatible image generation endpoint using Pollinations.ai."""
    body = await request.json()
    img_req = ImageRequest(**body)
    prompt = img_req.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Empty prompt")

    # Detect if Chinese and enhance prompt
    has_chinese = bool(_re.search(r'[一-鿿]', prompt))
    if has_chinese:
        prompt = f"high quality, detailed, {prompt}"

    urls = []
    for _ in range(img_req.n):
        url = _build_pollinations_url(prompt, img_req.size)
        urls.append({"url": url})

    client_ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else "")
    _record_request(img_req.prompt[:80], "pollinations", "image_generation", 0, True, client_ip=client_ip)

    return JSONResponse({
        "created": int(time.time()),
        "data": urls
    })


# ── Routes ──────────────────────────────────────────────────────────────────
@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """OpenAI 兼容接口。"""
    body = await request.json()
    raw_messages = body.get("messages", [])
    # Support explicit thinking flag from request body
    client_ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else "")
    ide_source = _detect_ide(raw_messages)

    # Rate limiting (skip for IDE clients)
    if not ide_source:
        import rate_limiter
        if not rate_limiter.check_rate_limit(client_ip):
            return JSONResponse(
                status_code=429,
                content={"error": {"message": "Rate limit exceeded. Try again later.", "type": "rate_limit_error"}})

    sys_prompt_preview = ""
    for m in raw_messages:
        if isinstance(m, dict) and m.get("role") == "system":
            sys_prompt_preview = (m.get("content", "") if isinstance(m.get("content"), str) else "")[:200]
            break

    # ── Vision detection on raw messages (before Pydantic parsing) ────────
    if smart_router.detect_vision_request(raw_messages):
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


@app.post("/v1/messages")
async def anthropic_messages(req: Request):
    """Anthropic 兼容接口（供 cc-switch Claude Code 使用）。支持流式和非流式、多模态。"""
    body = await req.json()

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
            duration_ms = int((time.time() - time.time()) * 1000)
            _record_request(last_user_query or "[vision]", backend_used, "vision", 0, True, client_ip=client_ip, ide_source=ide_source, sys_prompt_preview=sys_prompt_preview)
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


async def _anthropic_stream(req: ChatRequest, model: str, client_ip: str = "", ide_source: str = "", sys_prompt_preview: str = ""):
    """Anthropic SSE 流式响应（真流式透传 + fallback）。"""
    query = extract_query(req.messages)
    t0 = time.time()

    # ── Image generation intent detection ──────────────────────────────────
    is_image, image_prompt = smart_router.detect_image_intent(query)
    if is_image:
        image_url = _build_pollinations_url(image_prompt, "1024x1024")
        content = f"![image]({image_url})\n\n已为您生成图片，点击查看。"
        backend_used = "pollinations"
        duration_ms = int((time.time() - t0) * 1000)
        _record_request(query, backend_used, "image_generation", duration_ms, True, client_ip=client_ip, ide_source=ide_source, sys_prompt_preview=sys_prompt_preview)
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
        # ── Normal routing: do route first, then REAL STREAM ──────────────
        intent_used = smart_router.analyze(query, system_prompt=sys_prompt_preview, ide=ide_source)
        use_orch = needs_orchestration(query, intent_used)
        intent_name = intent_used.get("intent", "unknown") if isinstance(intent_used, dict) else "unknown"
        complexity = intent_used.get("complexity", 0.5) if isinstance(intent_used, dict) else 0.5

        if use_orch:
            # Orchestration: keep fake stream (multi-step pipeline)
            result = await asyncio.to_thread(orchestrate, query)
            content = result.get("answer", "")
            backend_used = result.get("backend", "orchestrator")
            thinking_handled = False  # use fake stream path below
        else:
            # SPECULATIVE STREAMING: predict backend + stream in parallel with routing
            msg_id = f"msg_{uuid.uuid4().hex[:24]}"
            total_text = ""

            # Emit message_start
            yield f"event: message_start\ndata: {json.dumps({'type':'message_start','message':{'id':msg_id,'type':'message','role':'assistant','model':model,'content':[],'stop_reason':None,'stop_sequence':None,'usage':{'input_tokens':10,'output_tokens':0}}})}\n\n"
            yield f"event: content_block_start\ndata: {json.dumps({'type':'content_block_start','index':0,'content_block':{'type':'text','text':''}})}\n\n"

            streamed_any = False
            async for backend_used, chunk in _speculative_stream_chunks(query, messages_to_dicts(req.messages), req.max_tokens or 4096, ide_source):
                streamed_any = True
                total_text += chunk
                yield f"event: content_block_delta\ndata: {json.dumps({'type':'content_block_delta','index':0,'delta':{'type':'text_delta','text':chunk}}, ensure_ascii=False)}\n\n"

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

            # Footer
            footer = f"\n\n---\n`[LiMa → {backend_used}]`"
            total_text += footer
            yield f"event: content_block_delta\ndata: {json.dumps({'type':'content_block_delta','index':0,'delta':{'type':'text_delta','text':footer}}, ensure_ascii=False)}\n\n"

            # End events
            yield f"event: content_block_stop\ndata: {json.dumps({'type':'content_block_stop','index':0})}\n\n"
            yield f"event: message_delta\ndata: {json.dumps({'type':'message_delta','delta':{'stop_reason':'end_turn','stop_sequence':None},'usage':{'output_tokens':len(total_text)//4}})}\n\n"
            yield f"event: message_stop\ndata: {json.dumps({'type':'message_stop'})}\n\n"

            duration_ms = int((time.time() - t0) * 1000)
            record_intent = intent_used if isinstance(intent_used, str) else intent_name
            _record_request(query, backend_used, record_intent, duration_ms, True, client_ip=client_ip, ide_source=ide_source, sys_prompt_preview=sys_prompt_preview)

            # Logging
            sys_prompt = extract_system_prompt(req.messages)
            if sys_prompt:
                try:
                    _log_sys_prompt(sys_prompt)
                except Exception:
                    pass
            try:
                if os.environ.get("DISTILL_LOG", "0") == "1":
                    smart_router._log_to_distill_queue(query, total_text, record_intent, backend_used)
            except Exception:
                pass
            return

        # ── Fake stream path: thinking mode, orchestration, or fallback ────
        # quality check + fallback for non-streaming content
        if not _quality_check(content, complexity, backend_used):
            fallback_backend = _default_route(query, ide_source) if backend_used == "unknown" else backend_used
            same_tier = _get_same_tier_backends(fallback_backend)
            fallback_found = False
            for alt in same_tier:
                alt_result = await _try_backend(alt, query, req.max_tokens or 4096)
                if alt_result and _quality_check(alt_result["answer"], complexity, alt):
                    content = alt_result["answer"]
                    backend_used = alt
                    fallback_found = True
                    break
            if not fallback_found:
                upgrade_chain = _get_upgrade_chain(fallback_backend)
                for upgraded in upgrade_chain:
                    up_result = await _try_backend(upgraded, query, req.max_tokens or 4096)
                    if up_result and _quality_check(up_result["answer"], complexity, upgraded):
                        content = up_result["answer"]
                        backend_used = upgraded
                        fallback_found = True
                        break
            if not fallback_found and not content:
                content = "当前所有服务暂时不可用，请稍后重试。"
                backend_used = "fallback_exhausted"

    # ── Build fake stream for thinking/orchestration/fallback ───────────────
    duration_ms = int((time.time() - t0) * 1000)
    record_intent = intent_used if isinstance(intent_used, str) else (intent_used.get("intent", "unknown") if isinstance(intent_used, dict) else "unknown")
    _record_request(query, backend_used, record_intent, duration_ms, True, client_ip=client_ip, ide_source=ide_source, sys_prompt_preview=sys_prompt_preview)

    if not content or not content.strip():
        content = _last_resort_call(messages_to_dicts(req.messages)) or "系统维护中，请稍后重试。"
        backend_used = backend_used or "empty_response"

    content += f"\n\n---\n`[LiMa → {backend_used}]`"
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

    sys_prompt = extract_system_prompt(req.messages)
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


async def _handle_chat(req: ChatRequest, fmt: str = "openai", request_model: str = None, client_ip: str = "", ide_source: str = "", sys_prompt_preview: str = ""):
    query = extract_query(req.messages)
    if not query.strip():
        raise HTTPException(status_code=400, detail="Empty query")

    chat_id = make_chat_id()
    t0 = time.time()

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
    elif USE_V3:
        result = await asyncio.to_thread(_v3_route, query,
            messages_to_dicts(req.messages),
            system_prompt=sys_prompt_preview, ide=ide_source,
            max_tokens=req.max_tokens or 4096)
    else:
        result = await asyncio.to_thread(smart_router.route, query, system_prompt=sys_prompt_preview, ide=ide_source, messages=messages_to_dicts(req.messages), prefer=prefer)

    content = result.get("answer", "")
    backend = result.get("backend", "unknown")
    total_ms = result.get("total_ms", 0)
    intent_name = intent.get("intent", "unknown") if isinstance(intent, dict) else "unknown"
    complexity = intent.get("complexity", 0.5) if isinstance(intent, dict) else 0.5

    # ── Fallback 层：质量检查 + 同层降级 + 跨层升级 ──
    if not _quality_check(content, complexity, backend):
        fallback_intent = intent_name if intent_name != "unknown" else "unknown"
        fallback_backend = _default_route(query, ide_source) if backend == "unknown" else backend

        # 同层降级：找同层级的其他后端
        same_tier = _get_same_tier_backends(fallback_backend)
        for alt in same_tier:
            alt_result = await _try_backend(alt, query, req.max_tokens or 1024)
            if alt_result and _quality_check(alt_result["answer"], complexity, alt):
                content = alt_result["answer"]
                backend = alt
                _record_fallback(query, fallback_backend, alt, f"fallback_same_tier_{fallback_intent}", ide_source)
                _record_request(query, backend, f"fallback_same_tier_{fallback_intent}", int((time.time() - t0) * 1000), True, client_ip=client_ip, ide_source=ide_source, sys_prompt_preview=sys_prompt_preview)
                if fmt == "anthropic":
                    return JSONResponse(build_anthropic_response(chat_id, content, backend, request_model or MODEL_ID))
                return JSONResponse(build_response(chat_id, content, backend, int((time.time() - t0) * 1000)))

        # 跨层升级：逐级升级
        upgrade_chain = _get_upgrade_chain(fallback_backend)
        for upgraded in upgrade_chain:
            up_result = await _try_backend(upgraded, query, req.max_tokens or 1024)
            if up_result and _quality_check(up_result["answer"], complexity, upgraded):
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
        return JSONResponse(_honest_failure_response(chat_id, fmt, request_model))

    duration_ms = int((time.time() - t0) * 1000)

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


# ── Real Streaming Bridge ─────────────────────────────────────────────────────
async def _real_stream_chunks(backend_name: str, msgs: list, max_tokens: int = 4096, ide: str = "unknown"):
    """Bridge sync call_api_stream() to async generator.
    Runs the sync generator in a thread, pushes chunks through a queue,
    yields text chunks asynchronously.
    """
    if USE_V3:
        async for chunk in streaming_mod.bridge_stream(
            backend_name, msgs, max_tokens, ide,
            call_stream_fn=_v3_call_stream,
            call_fn=_v3_call_api,
        ):
            yield chunk
        return

    import queue as queue_mod

    q: queue_mod.Queue = queue_mod.Queue()
    cancel_event = threading.Event()

    def _run():
        try:
            for chunk in smart_router.call_api_stream(backend_name, msgs, max_tokens, ide):
                if cancel_event.is_set():
                    return
                q.put(('chunk', chunk))
        except Exception as e:
            q.put(('error', e))
        finally:
            q.put(('done', None))

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    first_chunk_arrived = False
    timeout = 3.0
    start = time.time()

    while True:
        remaining = timeout - (time.time() - start)
        if remaining <= 0:
            break
        try:
            typ, val = q.get(timeout=min(remaining, 0.5))
        except queue_mod.Empty:
            continue
        if typ == 'done':
            if not first_chunk_arrived:
                result = await asyncio.to_thread(smart_router.call_api, backend_name, msgs, max_tokens, ide)
                if result and not str(result).startswith('[ERR]'):
                    yield str(result)
                return
            return
        if typ == 'chunk':
            first_chunk_arrived = True
            yield val

    if not first_chunk_arrived:
        cancel_event.set()
        result = await asyncio.to_thread(smart_router.call_api, backend_name, msgs, max_tokens, ide)
        if result and not str(result).startswith('[ERR]'):
            yield str(result)
        return

    # Continue consuming remaining chunks (with timeout to prevent hang)
    while True:
        try:
            typ, val = await asyncio.to_thread(q.get, timeout=30)
        except queue_mod.Empty:
            break
        if typ == 'done':
            break
        if typ == 'chunk':
            yield val


# ── Speculative Streaming ─────────────────────────────────────────────────────
async def _speculative_stream_chunks(query: str, msgs: list, max_tokens: int = 4096, ide: str = "unknown"):
    """Speculative streaming: predict backend and start streaming immediately,
    while routing runs in parallel. If prediction is wrong, switch to correct backend.

    Yields (backend_name, text_chunk) tuples.
    """
    if USE_V3:
        async for item in streaming_mod.speculative_stream(
            query, msgs, max_tokens, ide,
            predict_fn=_v3_predict,
            select_fn=_v3_select,
            call_stream_fn=_v3_call_stream,
            call_fn=_v3_call_api,
        ):
            yield item
        return
    predicted = smart_router.predict_fast_backend(query)
    predicted_msgs = msgs if msgs else [{"role": "user", "content": query}]

    route_task = asyncio.create_task(
        asyncio.to_thread(smart_router.select_backend, query, system_prompt="", ide=ide, messages=msgs)
    )

    actual_backend = None
    actual_msgs = None
    prediction_wrong = False

    try:
        async for chunk in _real_stream_chunks(predicted, predicted_msgs, max_tokens, ide):
            # Check if routing completed mid-stream
            if route_task.done() and actual_backend is None:
                try:
                    actual_backend, actual_msgs = route_task.result()
                except Exception as e:
                    print(f'[SPEC] route_task failed: {e}', file=__import__("sys").stderr)
                    actual_backend = predicted
                    actual_msgs = predicted_msgs

                if actual_backend != predicted:
                    prediction_wrong = True
                    break
            yield (actual_backend or predicted, chunk)

        # Stream exhausted naturally — prediction was correct (or routing not done yet)
        if not prediction_wrong:
            if actual_backend is None:
                try:
                    actual_backend, actual_msgs = await route_task
                except Exception:
                    actual_backend = predicted
                    actual_msgs = predicted_msgs
            return

        # Prediction wrong — switch to actual backend
        async for chunk in _real_stream_chunks(actual_backend, actual_msgs, max_tokens, ide):
            yield (actual_backend, chunk)

    finally:
        if not route_task.done():
            route_task.cancel()
            try:
                await route_task
            except (asyncio.CancelledError, Exception):
                pass


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
            elif USE_V3:
                result = await asyncio.to_thread(_v3_route, query, messages,
                    system_prompt=sys_prompt_preview, ide=ide_source,
                    max_tokens=4096)
            else:
                result = await asyncio.to_thread(smart_router.route, query, system_prompt=sys_prompt_preview, ide=ide_source, messages=messages, prefer=prefer)
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
    async for backend, chunk in _speculative_stream_chunks(query, messages, 4096, ide_source):
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


@app.get("/api/live-key")
async def live_key():
    """返回 Gemini Live API key（供视频通话前端使用）。"""
    key = os.environ.get("GOOGLE_AI_KEY", "")
    if not key:
        raise HTTPException(status_code=503, detail="Gemini key not configured")
    return {"key": key, "model": "models/gemini-2.0-flash-live-001"}


@app.get("/v1/status")
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


# ── Startup ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print('[LiMa] Warming up router model...', file=sys.stderr)
    smart_router.warmup_router_model()
    uvicorn.run(app, host="0.0.0.0", port=8080)
