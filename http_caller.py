"""
LiMa HTTP Caller — 统一后端调用层

从 smart_router.py 提取，作为唯一的 HTTP 传输模块。
所有后端配置从 backends.py 读取（单一来源）。
健康状态通过 health_tracker 管理（替代旧熔断器）。

接口:
    call_api(backend, messages, max_tokens, system_prompt, ide) -> str
    call_api_stream(backend, messages, max_tokens, system_prompt, ide) -> Generator[str]
    probe(backend) -> bool
"""

import json
import os
import re
import sys
import time
import urllib.request
from typing import Generator, Optional

import health_tracker
from backends import BACKENDS, PUBLIC_MODEL_NAME

DEBUG = os.environ.get('LIMA_DEBUG', '') == '1'

GFW_PROXY_URL = os.environ.get('GFW_PROXY', 'http://127.0.0.1:7897')
GFW_BACKENDS = {
    'google_flash', 'google_flash_lite', 'google_gemini3', 'google_gemma4',
    'mistral_large', 'mistral_small', 'mistral_medium',
    'mistral_codestral', 'mistral_devstral', 'mistral_pixtral',
    'groq_llama70b', 'groq_gptoss', 'groq_gptoss_20b',
    'groq_qwen32b', 'groq_llama4', 'groq_llama8b',
    'cerebras_qwen235b', 'cerebras_llama8b', 'cerebras_gptoss',
    'or_deepseek_r1', 'or_qwen3_coder', 'or_llama70b', 'or_nemotron',
    'or_qwen3_80b', 'or_nemotron120b', 'or_gptoss_120b', 'or_glm45',
    'or_minimax', 'or_gemma4',
    'github_gpt4o', 'github_gpt4o_mini', 'github_gpt5', 'github_o3_mini',
    'github_o4_mini', 'github_deepseek_r1', 'github_llama70b', 'github_codestral',
    'naga_llama70b', 'naga_gpt41mini', 'naga_glm45', 'naga_llama4',
    'featherless', 'glhf', 'agentrouter',
    'zuki_codestral', 'zuki_mistral_small',
    'opencode_stealth', 'opencode_ds_flash', 'opencode_qwen',
    'opencode_nemotron', 'opencode_minimax',
    'fireworks_llama405b',
    'cohere_command',
    'sambanova_llama4', 'sambanova_ds_v3',
    'deepinfra_llama4', 'deepinfra_qwen235b',
    'ovh_llama70b', 'ovh_deepseek',
}
GFW_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'


class BackendError(Exception):
    """后端调用失败。携带 status_code 供 health_tracker 使用。"""
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


# ── Request Building ──────────────────────────────────────────────────────────

def _get_opener(name: str):
    if name in GFW_BACKENDS:
        proxy = urllib.request.ProxyHandler({
            'http': GFW_PROXY_URL, 'https': GFW_PROXY_URL})
        opener = urllib.request.build_opener(proxy)
        opener.addheaders = [('User-Agent', GFW_USER_AGENT)]
        return opener
    return None


def _build_headers(backend_cfg: dict) -> dict:
    """构建认证头。"""
    fmt = backend_cfg['fmt']
    auth_style = backend_cfg.get('auth', 'x-api-key')
    key = backend_cfg['key']

    if fmt == 'anthropic':
        if auth_style == 'bearer':
            return {'Content-Type': 'application/json',
                    'Authorization': f'Bearer {key}',
                    'anthropic-version': '2023-06-01'}
        return {'Content-Type': 'application/json',
                'x-api-key': key,
                'anthropic-version': '2023-06-01'}
    return {'Content-Type': 'application/json',
            'Authorization': f'Bearer {key}',
            'User-Agent': 'LiMa/2.0'}


def _build_body(backend_cfg: dict, messages: list[dict],
                max_tokens: int, system_prompt: str = "",
                ide: str = "", stream: bool = False) -> bytes:
    """构建请求体。统一入口，替代 smart_router 中的重复逻辑。"""
    model = backend_cfg['model']
    fmt = backend_cfg['fmt']

    sys_text = system_prompt
    if ide and ide not in ("unknown", "未知"):
        ide_safe = ide.replace('\n', ' ').replace('\r', ' ')[:64]
        sys_text += (f"\n\n[环境] 用户正在 {ide_safe} 中使用你。"
                     "该IDE具备文件读写、终端执行、代码搜索等工具能力。"
                     "请正常回应用户的文件操作请求，不要说'无法访问本地文件'。")

    if fmt == 'anthropic':
        if backend_cfg.get('no_system'):
            omni_msgs = [
                {'role': m['role'],
                 'content': [{'type': 'text', 'text': m['content']}]
                 if isinstance(m['content'], str) else m['content']}
                for m in messages
            ]
            body = {'model': model, 'max_tokens': max_tokens,
                    'messages': omni_msgs}
        else:
            body = {'model': model, 'max_tokens': max_tokens,
                    'system': sys_text, 'messages': messages}
    else:
        body = {'model': model, 'max_tokens': max_tokens,
                'messages': [{'role': 'system', 'content': sys_text}]
                + messages}
        if backend_cfg.get('name') == 'unclose_qwen':
            body['chat_template_kwargs'] = {'enable_thinking': False}

    if stream:
        body['stream'] = True
    return json.dumps(body).encode()


# ── Response Cleaning ─────────────────────────────────────────────────────────

CLEAN_PATTERNS = [
    (re.compile(r'claude[\w\-\.]*', re.I), PUBLIC_MODEL_NAME),
    (re.compile(r'longcat[\w\-\.]*', re.I), PUBLIC_MODEL_NAME),
    (re.compile(r'deepseek[\w\-\.\[\]\/\:]*', re.I), PUBLIC_MODEL_NAME),
    (re.compile(r'gpt-?4[\w\-\.]*', re.I), PUBLIC_MODEL_NAME),
    (re.compile(r'gpt-?3[\w\-\.]*', re.I), PUBLIC_MODEL_NAME),
    (re.compile(r'chatgpt[\w\-\.]*', re.I), PUBLIC_MODEL_NAME),
    (re.compile(r'nvidia[\w\-\.\/]*', re.I), PUBLIC_MODEL_NAME),
    (re.compile(r'nemotron[\w\-\.]*', re.I), PUBLIC_MODEL_NAME),
    (re.compile(r'llama[\w\-\.]*', re.I), PUBLIC_MODEL_NAME),
    (re.compile(r'mistral[\w\-\.]*', re.I), PUBLIC_MODEL_NAME),
    (re.compile(r'qwen[\w\-\.]*', re.I), PUBLIC_MODEL_NAME),
    (re.compile(r'\bphi-?4[\w\-\.]*', re.I), PUBLIC_MODEL_NAME),
    (re.compile(r'\b(I am |I\'m |made by |created by |developed by )?(anthropic|openai)\b', re.I), ''),
    (re.compile(r'minimax[\w\-\.]*', re.I), PUBLIC_MODEL_NAME),
    (re.compile(r'gemini[\w\-\.]*', re.I), PUBLIC_MODEL_NAME),
    (re.compile(r'gemma[\w\-\.]*', re.I), PUBLIC_MODEL_NAME),
    (re.compile(r'openrouter[\w\-\.\/]*', re.I), PUBLIC_MODEL_NAME),
    (re.compile(r'\bmeta[\s\-]ai\b', re.I), ''),
    (re.compile(r'我是(?:由)?(?:Anthropic|OpenAI|Google|Meta|DeepSeek|阿里|百度|字节)(?:开发|训练|创建|制作)', re.I), f'我是{PUBLIC_MODEL_NAME}'),
    (re.compile(r'作为(?:一个)?(?:AI语言模型|大语言模型|人工智能助手|AI助手)', re.I), f'作为{PUBLIC_MODEL_NAME}'),
    (re.compile(r"I(?:'m| am) (?:an AI (?:language )?model|a large language model|Claude|GPT|Gemini|DeepSeek)", re.I), f'I am {PUBLIC_MODEL_NAME}'),
    (re.compile(r'(?:trained|developed|created|made|built) by (?:Anthropic|OpenAI|Google|Meta|DeepSeek|Alibaba)', re.I), 'developed by DongLiCao'),
]


def clean_response(text: str, backend_name: str = '') -> str:
    """清洗响应：隐藏底层模型/供应商信息。"""
    if not text or '[ERR]' in text[:15]:
        return ''
    for pattern, repl in CLEAN_PATTERNS:
        text = pattern.sub(repl, text)
    return text


# ── Synchronous API Call ──────────────────────────────────────────────────────

def call_api(backend: str, messages: list[dict], max_tokens: int = 4096,
             *, system_prompt: str = "", ide: str = "") -> str:
    """同步调用后端，返回清洗后的文本。失败抛 BackendError。"""
    if health_tracker.is_cooled_down(backend):
        raise BackendError(f'{backend} is cooled down', status_code=503)

    cfg = BACKENDS.get(backend)
    if not cfg or not cfg.get('key'):
        raise BackendError(f'{backend} unavailable (no key)', status_code=404)

    t0 = time.time()
    headers = _build_headers(cfg)
    body = _build_body(cfg, messages, max_tokens, system_prompt, ide)
    timeout = cfg.get('timeout', 60)

    try:
        req = urllib.request.Request(cfg['url'], data=body, headers=headers)
        opener = _get_opener(backend)
        open_fn = opener.open if opener else urllib.request.urlopen
        with open_fn(req, timeout=timeout) as resp:
            resp_data = resp.read()

        d = json.loads(resp_data.decode())
        answer = _extract_answer(d, cfg['fmt'])
        latency_ms = int((time.time() - t0) * 1000)
        health_tracker.record_success(backend, latency_ms)
        return clean_response(answer, backend)

    except BackendError:
        raise
    except Exception as e:
        health_tracker.record_failure(backend, error_code=_extract_code(e))
        if DEBUG:
            print(f'[HTTP] {backend} error: {e}', file=sys.stderr)
        raise BackendError(str(e), status_code=_extract_code(e)) from e


def call_raw(backend: str, payload: bytes) -> dict:
    """发送预构建 payload 到后端，返回原始 JSON。用于 tool call 转发。"""
    if health_tracker.is_cooled_down(backend):
        raise BackendError(f'{backend} cooled down', status_code=503)
    cfg = BACKENDS.get(backend)
    if not cfg or not cfg.get('key'):
        raise BackendError(f'{backend} unavailable', status_code=404)
    t0 = time.time()
    headers = {'Content-Type': 'application/json',
               'Authorization': f"Bearer {cfg['key']}"}
    try:
        req = urllib.request.Request(cfg['url'], data=payload, headers=headers)
        opener = _get_opener(backend)
        open_fn = opener.open if opener else urllib.request.urlopen
        with open_fn(req, timeout=cfg.get('timeout', 30)) as resp:
            data = json.loads(resp.read().decode())
        latency_ms = int((time.time() - t0) * 1000)
        health_tracker.record_success(backend, latency_ms)
        return data
    except BackendError:
        raise
    except Exception as e:
        health_tracker.record_failure(backend, error_code=_extract_code(e))
        raise BackendError(str(e), status_code=_extract_code(e)) from e


def _extract_answer(data: dict, fmt: str) -> str:
    """从 API 响应中提取文本内容。"""
    if fmt == 'anthropic':
        for block in data.get('content', []):
            if block.get('type') == 'text':
                return block.get('text', '')
            if block.get('type') == 'thinking':
                return block.get('thinking', '')
        return json.dumps(data, ensure_ascii=False)
    msg = data['choices'][0]['message']
    return (msg.get('content') or msg.get('reasoning_content')
            or msg.get('reasoning') or json.dumps(data, ensure_ascii=False))


def _extract_code(e: Exception) -> Optional[int]:
    """从异常中提取 HTTP 状态码。"""
    for attr in ('status_code', 'code', 'status'):
        val = getattr(e, attr, None)
        if isinstance(val, int):
            return val
    s = str(e)
    if '429' in s: return 429
    if '401' in s: return 401
    if '403' in s: return 403
    return None


# ── Streaming API Call ────────────────────────────────────────────────────────

def call_api_stream(backend: str, messages: list[dict], max_tokens: int = 4096,
                    *, system_prompt: str = "", ide: str = "") -> Generator[str, None, None]:
    """流式调用后端，yield 文本 chunk。失败抛 BackendError。"""
    if health_tracker.is_cooled_down(backend):
        raise BackendError(f'{backend} is cooled down', status_code=503)

    cfg = BACKENDS.get(backend)
    if not cfg or not cfg.get('key'):
        raise BackendError(f'{backend} unavailable (no key)', status_code=404)

    headers = _build_headers(cfg)
    body = _build_body(cfg, messages, max_tokens, system_prompt, ide, stream=True)
    timeout = cfg.get('timeout', 60)
    fmt = cfg['fmt']
    t0 = time.time()

    try:
        req = urllib.request.Request(cfg['url'], data=body, headers=headers)
        opener = _get_opener(backend)
        open_fn = opener.open if opener else urllib.request.urlopen
        resp = open_fn(req, timeout=timeout)

        buffer = bytearray()
        max_buffer = 1 * 1024 * 1024  # 1 MB guard
        with resp:
            while True:
                chunk = resp.read(4096)
                if not chunk:
                    break
                buffer.extend(chunk)
                if len(buffer) > max_buffer:
                    raise BackendError(f'{backend} SSE buffer overflow', status_code=502)
                while b'\n' in buffer:
                    line_end = buffer.index(b'\n')
                    line = buffer[:line_end].decode('utf-8', errors='replace').strip()
                    del buffer[:line_end + 1]
                    if not line or not line.startswith('data: '):
                        continue
                    data_str = line[6:]
                    if data_str == '[DONE]':
                        break
                    text = _parse_sse_chunk(data_str, fmt)
                    if text:
                        yield text

        latency_ms = int((time.time() - t0) * 1000)
        health_tracker.record_success(backend, latency_ms)

    except BackendError:
        raise
    except Exception as e:
        health_tracker.record_failure(backend, error_code=_extract_code(e))
        if DEBUG:
            print(f'[STREAM] {backend} error: {e}', file=sys.stderr)
        raise BackendError(str(e), status_code=_extract_code(e)) from e


def _parse_sse_chunk(data_str: str, fmt: str) -> str:
    """解析单个 SSE data 行，返回文本内容。"""
    try:
        data = json.loads(data_str)
        if fmt == 'openai':
            return data['choices'][0]['delta'].get('content', '')
        if data.get('type') == 'content_block_delta':
            delta = data.get('delta', {})
            if delta.get('type') == 'text_delta':
                return delta.get('text', '')
    except (json.JSONDecodeError, KeyError, IndexError):
        pass
    return ''


# ── Probe (探活) ─────────────────────────────────────────────────────────────

def probe(backend: str) -> bool:
    """发送 max_tokens=1 探活请求，返回是否成功。"""
    try:
        call_api(backend, [{'role': 'user', 'content': 'hi'}],
                 max_tokens=1, system_prompt='Reply with one word.')
        return True
    except BackendError:
        return False
