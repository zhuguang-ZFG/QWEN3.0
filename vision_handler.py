"""vision_handler.py — Vision (Photo-to-Answer) detection, format conversion, routing, and streaming."""
import json, time, asyncio, sys, os

import health_tracker
from http_caller import clean_response
from backends_constants import VISION_BACKENDS
from backends_registry import BACKENDS

DEBUG = os.environ.get('LIMA_DEBUG', '') == '1'

MODEL_ID = "lima-1.3"
VISION_SYSTEM_PROMPT = "你是一位耐心的老师。用户上传了一道题目的图片。请：1. 识别题目内容 2. 分步骤解答 3. 给出最终答案。如果是选择题，明确指出正确选项。"

def _split_sentences(text: str) -> list[str]:
    if not text: return [""]
    chunks, current = [], ""
    for char in text:
        current += char
        if char in ("。", "！", "？", "\n", ".", "!", "?") and len(current) > 5:
            chunks.append(current); current = ""
    if current: chunks.append(current)
    return chunks if chunks else [text]

def build_stream_chunk(chat_id: str, content: str, finish: bool = False) -> str:
    delta = {} if finish else {"content": content}
    chunk = {"id": chat_id, "object": "chat.completion.chunk",
             "created": int(time.time()), "model": MODEL_ID,
             "choices": [{"index": 0, "delta": delta if not finish else {},
                          "finish_reason": "stop" if finish else None}]}
    return f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

def detect_vision_request(messages: list) -> bool:
    """Detect if any message contains image content (OpenAI vision format: content list with image_url blocks)."""
    if not messages: return False
    for msg in messages:
        if not isinstance(msg, dict): continue
        content = msg.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "image_url":
                    return True
    return False

def convert_openai_vision_to_anthropic(messages: list) -> list:
    """Convert OpenAI vision format to Anthropic: image_url -> image source blocks."""
    converted = []
    for msg in messages:
        if not isinstance(msg, dict): continue
        role = msg.get("role", "user")
        content = msg.get("content")
        if isinstance(content, str):
            converted.append({"role": role, "content": [{"type": "text", "text": content}]})
        elif isinstance(content, list):
            new_blocks = []
            for block in content:
                if not isinstance(block, dict): continue
                if block.get("type") == "text":
                    new_blocks.append({"type": "text", "text": block.get("text", "")})
                elif block.get("type") == "image_url":
                    image_url = block.get("image_url", {})
                    url = image_url.get("url", "")
                    if url.startswith("data:"):
                        header, _, data = url.partition(",")
                        media_type = header.split(":")[1].split(";")[0] if ":" in header else "image/jpeg"
                        new_blocks.append({"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}})
                    else:
                        new_blocks.append({"type": "text", "text": f"[Image URL: {url}]"})
                else:
                    new_blocks.append(block)
            converted.append({"role": role, "content": new_blocks})
        else:
            converted.append({"role": role, "content": [{"type": "text", "text": str(content)}]})
    return converted

async def _vision_route(messages: list, max_tokens: int = 4096, ide: str = "unknown") -> dict | None:
    """Route vision requests to a multimodal backend. Returns result dict or None."""
    for backend_name in VISION_BACKENDS:
        if backend_name not in BACKENDS: continue
        if not BACKENDS[backend_name].get('key'): continue
        if health_tracker.is_cooled_down(backend_name): continue
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(_call_vision_backend, backend_name, messages, max_tokens, ide),
                timeout=60.0)
            if result and not (isinstance(result, str) and (result.startswith("[ERR]") or "暂时不可用" in result)):
                return {"answer": result, "backend": backend_name}
        except (asyncio.TimeoutError, Exception) as e:
            if DEBUG: print(f"[VISION] {backend_name} failed: {e}", file=sys.stderr)
            health_tracker.record_failure(backend_name, error_code=None)
            continue
    return None

def _call_vision_backend(backend_name: str, messages: list, max_tokens: int, ide: str) -> str | None:
    """Call a vision-capable backend with image content."""
    import urllib.request as _ur
    b = BACKENDS[backend_name]
    fmt = b.get('fmt', 'openai')
    auth_style = b.get('auth', 'x-api-key')
    if fmt == 'anthropic':
        anthropic_msgs = convert_openai_vision_to_anthropic(messages)
        if b.get('no_system'):
            system_text_block = {"type": "text", "text": VISION_SYSTEM_PROMPT}
            if anthropic_msgs and anthropic_msgs[0]["role"] == "user":
                anthropic_msgs[0]["content"].insert(0, system_text_block)
            else:
                anthropic_msgs.insert(0, {"role": "user", "content": [system_text_block]})
            body = {'model': b['model'], 'max_tokens': max_tokens, 'messages': anthropic_msgs}
        else:
            body = {'model': b['model'], 'max_tokens': max_tokens,
                    'system': VISION_SYSTEM_PROMPT, 'messages': anthropic_msgs}
        p = json.dumps(body).encode()
        if auth_style == 'bearer':
            h = {'Content-Type': 'application/json',
                 'Authorization': f"Bearer {b['key']}", 'anthropic-version': '2023-06-01'}
        else:
            h = {'Content-Type': 'application/json',
                 'x-api-key': b['key'], 'anthropic-version': '2023-06-01'}
    else:
        openai_msgs = [{'role': 'system', 'content': VISION_SYSTEM_PROMPT}] + messages
        body = {'model': b['model'], 'max_tokens': max_tokens, 'messages': openai_msgs}
        p = json.dumps(body).encode()
        h = {'Content-Type': 'application/json', 'Authorization': f"Bearer {b['key']}"}
    try:
        req = _ur.Request(b['url'], data=p, headers=h)
        _timeout = b.get('timeout', 60)
        with _ur.urlopen(req, timeout=_timeout) as resp:
            d = json.loads(resp.read().decode())
        if fmt == 'anthropic': answer = d['content'][0].get('text', '')
        else: answer = d['choices'][0]['message'].get('content', '')
        health_tracker.record_success(backend_name, 0)
        return clean_response(answer, backend_name)
    except Exception as e:
        if DEBUG: print(f'[VISION] {backend_name} call error: {e}', file=sys.stderr)
        health_tracker.record_failure(backend_name, error_code=None)
        return None

async def _stream_vision_response(chat_id: str, content: str):
    """Stream a vision response in OpenAI SSE format."""
    sentences = _split_sentences(content)
    for sentence in sentences:
        yield build_stream_chunk(chat_id, sentence)
        await asyncio.sleep(0.02)
    yield build_stream_chunk(chat_id, "", finish=True)
    yield "data: [DONE]\n\n"
