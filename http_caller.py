"""
LiMa HTTP Caller — 统一后端调用层

从 smart_router.py 提取，作为唯一的 HTTP 传输模块。
所有后端配置从 backends.py 读取（单一来源）。
健康状态通过 health_tracker 管理（替代旧熔断器）。

接口:
    call_api(backend, messages, max_tokens, system_prompt, ide) -> str
    call_api_async(...) -> Awaitable[str]
    call_api_stream(backend, messages, max_tokens, system_prompt, ide) -> Generator[str]
    call_api_stream_async(...) -> AsyncIterator[str]
    probe(backend) -> bool
"""

import json
import logging
import os
import sys
import time
from typing import AsyncIterator, Generator, Optional

import httpx

import health_tracker
import key_pool
from backends import BACKENDS, GFW_BACKENDS, infer_key_pool_provider
from response_cleaner import clean_response, _clean_brand_only, _is_backend_error

logger = logging.getLogger(__name__)

DEBUG = os.environ.get('LIMA_DEBUG', '') == '1'

GFW_PROXY_URL = os.environ.get('GFW_PROXY', 'http://127.0.0.1:7897')
GFW_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'


class BackendError(Exception):
    """后端调用失败。携带 status_code 供 health_tracker 使用。"""
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


# ── Request Building ──────────────────────────────────────────────────────────

def _build_client(backend: str, timeout: float) -> httpx.Client:
    """Build httpx Client with proxy for GFW backends."""
    if backend in GFW_BACKENDS:
        return httpx.Client(
            proxy=GFW_PROXY_URL,
            headers={'User-Agent': GFW_USER_AGENT},
            timeout=httpx.Timeout(timeout, connect=10.0),
        )
    return httpx.Client(timeout=httpx.Timeout(timeout, connect=10.0))


def _build_async_client(backend: str, timeout: float) -> httpx.AsyncClient:
    """Build httpx AsyncClient with proxy for GFW backends."""
    if backend in GFW_BACKENDS:
        return httpx.AsyncClient(
            proxy=GFW_PROXY_URL,
            headers={'User-Agent': GFW_USER_AGENT},
            timeout=httpx.Timeout(timeout, connect=10.0),
        )
    return httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=10.0))


def _build_headers(backend_cfg: dict, key: str = None) -> dict:
    """构建认证头。"""
    fmt = backend_cfg['fmt']
    auth_style = backend_cfg.get('auth', 'x-api-key')
    key = backend_cfg['key'] if key is None else key

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


def _key_pool_provider(backend: str, backend_cfg: dict) -> str:
    return infer_key_pool_provider(backend, backend_cfg)


def _select_key(backend: str, backend_cfg: dict) -> tuple[str, str]:
    provider = _key_pool_provider(backend, backend_cfg)
    if provider:
        pool_configured = key_pool.ensure_env_pool(provider)
        if pool_configured:
            if key_pool.is_exhausted(provider):
                return '', provider
            selected = key_pool.get_key(provider)
            if selected:
                return selected, provider
    return backend_cfg.get('key', ''), provider


def _has_key(backend: str, backend_cfg: dict) -> bool:
    selected, _provider = _select_key(backend, backend_cfg)
    return bool(selected)


def _report_key_result(provider: str, key: str, success: bool,
                       error_code: int = 0, retry_after: int = 0) -> None:
    if not provider or not key:
        return
    if success:
        key_pool.report_key_result(provider, key, True)
    else:
        key_pool.report_key_result(
            provider, key, False,
            error_code=error_code or 0,
            retry_after=retry_after,
        )


def _extract_retry_after(e: Exception) -> int:
    if isinstance(e, httpx.HTTPStatusError):
        try:
            return int(e.response.headers.get('Retry-After', 0))
        except (TypeError, ValueError):
            return 0
    headers = getattr(e, 'headers', None)
    value = None
    if headers:
        try:
            value = headers.get('Retry-After')
        except AttributeError:
            value = None
    try:
        return int(value) if value else 0
    except (TypeError, ValueError):
        return 0


def _build_body(backend_cfg: dict, messages: list[dict],
                max_tokens: int, system_prompt: str = "",
                ide: str = "", stream: bool = False) -> bytes:
    """构建请求体。统一入口，替代 smart_router 中的重复逻辑。"""
    model = backend_cfg['model']
    fmt = backend_cfg['fmt']

    sys_text = system_prompt
    if ide and ide not in ("unknown", "未知"):
        from prompt_engineering.layers import compose_system_prompt
        scenario = "coding" if fmt != "anthropic" or ide else "chat"
        sys_text = compose_system_prompt(
            ide=ide,
            scenario=scenario,
            code_context=system_prompt if system_prompt else "",
        )

    # ── Integration: Cache Optimization (Phase P2) — stable prefix first ──
    try:
        from context_pipeline.cache import optimize_for_prefix_cache
        if sys_text and messages:
            sys_text, messages = optimize_for_prefix_cache(sys_text, messages)
    except ImportError:
        pass
    except Exception as exc:
        logger.warning("prefix cache optimization failed: %s", exc, exc_info=True)

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
        if backend_cfg.get('no_system'):
            outgoing = [dict(m) for m in messages]
            if sys_text and outgoing:
                for msg in outgoing:
                    if msg.get('role') == 'user':
                        content = msg.get('content', '')
                        if isinstance(content, str):
                            msg['content'] = f"{sys_text}\n\n{content}"
                        elif isinstance(content, list):
                            msg['content'] = (
                                [{'type': 'text', 'text': sys_text}] + content)
                        break
            body = {'model': model, 'max_tokens': max_tokens,
                    'messages': outgoing}
        else:
            body = {'model': model, 'max_tokens': max_tokens,
                    'messages': [{'role': 'system', 'content': sys_text}]
                    + messages}

    # 通用参数注入：从后端配置的 extra_body 字段合并
    extra = backend_cfg.get('extra_body')
    if extra and isinstance(extra, dict):
        body.update(extra)

    if stream or backend_cfg.get('force_stream_param'):
        body['stream'] = bool(stream)
    return json.dumps(body).encode()


# ── Synchronous API Call ──────────────────────────────────────────────────────

def call_api(backend: str, messages: list[dict], max_tokens: int = 4096,
             *, system_prompt: str = "", ide: str = "") -> str:
    """同步调用后端，返回清洗后的文本。失败抛 BackendError。"""
    cfg = BACKENDS.get(backend)
    if not cfg:
        raise BackendError(f'{backend} unavailable (no key)', status_code=404)
    selected_key, key_provider = _select_key(backend, cfg)
    if not selected_key:
        raise BackendError(f'{backend} unavailable (no key)', status_code=404)

    if health_tracker.is_cooled_down(backend):
        raise BackendError(f'{backend} is cooled down', status_code=503)

    # ── Integration: Artifact Handle (Phase P5) — large context → handle ──
    try:
        from context_pipeline.artifact import should_use_handle, create_handle
        for i, msg in enumerate(messages):
            if isinstance(msg, dict) and msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str) and should_use_handle(content):
                    messages[i] = {**msg, "content": create_handle(content)}
    except ImportError:
        pass

    t0 = time.time()
    headers = _build_headers(cfg, key=selected_key)
    body = _build_body(cfg, messages, max_tokens, system_prompt, ide)
    timeout = cfg.get('timeout', 60)

    try:
        with _build_client(backend, timeout) as client:
            resp = client.post(cfg['url'], content=body, headers=headers)
            resp.raise_for_status()
            d = resp.json()

        answer = _extract_answer(d, cfg['fmt'])

        if _is_backend_error(answer):
            health_tracker.record_failure(
                backend, error_code=429, error_text=answer)
            raise BackendError(
                f'{backend} returned error response: {answer[:60]}',
                status_code=429)

        latency_ms = int((time.time() - t0) * 1000)
        health_tracker.record_success(backend, latency_ms)
        _report_key_result(key_provider, selected_key, True)
        cleaned = clean_response(answer, backend)
        health_tracker.record_response_quality(
            backend, len(cleaned) if cleaned else 0)

        # Token telemetry
        p_tok, c_tok = _extract_usage(d, cfg['fmt'])
        try:
            import budget_manager
            budget_manager.record_token_usage(backend, p_tok, c_tok)
        except ImportError:
            pass

        # Emit backend_call_event to observability (M6-S3)
        try:
            from observability.metrics import record as _obs_record
            from observability.events import backend_call_event
            _obs_record(backend_call_event("", backend, "", latency_ms=latency_ms))
        except ImportError:
            pass

        return cleaned

    except BackendError as e:
        _report_key_result(
            key_provider, selected_key, False,
            error_code=e.status_code or 0, retry_after=0)
        _emit_backend_error(backend, e.status_code, str(e))
        raise
    except httpx.HTTPStatusError as e:
        error_code = e.response.status_code
        health_tracker.record_failure(
            backend, error_code=error_code, error_text=str(e))
        _report_key_result(
            key_provider, selected_key, False,
            error_code=error_code, retry_after=_extract_retry_after(e))
        _emit_backend_error(backend, error_code, str(e))
        raise BackendError(str(e), status_code=error_code) from e
    except Exception as e:
        error_code = _extract_code(e)
        health_tracker.record_failure(
            backend, error_code=error_code, error_text=str(e))
        _report_key_result(
            key_provider, selected_key, False,
            error_code=error_code or 0, retry_after=_extract_retry_after(e))
        _emit_backend_error(backend, error_code, str(e))
        if DEBUG:
            print(f'[HTTP] {backend} error: {e}', file=sys.stderr)
        raise BackendError(str(e), status_code=error_code) from e


def call_raw(backend: str, payload: bytes) -> dict:
    """发送预构建 payload 到后端，返回原始 JSON。用于 tool call 转发。"""
    cfg = BACKENDS.get(backend)
    if not cfg:
        raise BackendError(f'{backend} unavailable', status_code=404)
    selected_key, key_provider = _select_key(backend, cfg)
    if not selected_key:
        raise BackendError(f'{backend} unavailable', status_code=404)
    t0 = time.time()
    headers = {'Content-Type': 'application/json',
               'Authorization': f"Bearer {selected_key}"}
    try:
        with _build_client(backend, cfg.get('timeout', 30)) as client:
            resp = client.post(cfg['url'], content=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        latency_ms = int((time.time() - t0) * 1000)
        health_tracker.record_success(backend, latency_ms)
        _report_key_result(key_provider, selected_key, True)
        return data
    except BackendError as e:
        _report_key_result(
            key_provider, selected_key, False,
            error_code=e.status_code or 0, retry_after=0)
        raise
    except httpx.HTTPStatusError as e:
        error_code = e.response.status_code
        health_tracker.record_failure(
            backend, error_code=error_code, error_text=str(e))
        _report_key_result(
            key_provider, selected_key, False,
            error_code=error_code, retry_after=_extract_retry_after(e))
        raise BackendError(str(e), status_code=error_code) from e
    except Exception as e:
        error_code = _extract_code(e)
        health_tracker.record_failure(
            backend, error_code=error_code, error_text=str(e))
        _report_key_result(
            key_provider, selected_key, False,
            error_code=error_code or 0, retry_after=_extract_retry_after(e))
        raise BackendError(str(e), status_code=error_code) from e


def _extract_answer(data: dict, fmt: str) -> str:
    """从 API 响应中提取文本内容。"""
    if fmt == 'anthropic':
        text_content = ''
        for block in data.get('content', []):
            if block.get('type') == 'text':
                text_content = block.get('text', '')
                break
        if text_content:
            return text_content
        for block in data.get('content', []):
            if block.get('type') == 'thinking':
                return block.get('thinking', '')
        return ''
    msg = data['choices'][0]['message']
    return (msg.get('content') or msg.get('reasoning_content')
            or msg.get('reasoning') or '')


def _extract_usage(data: dict, fmt: str) -> tuple[int, int]:
    """从 API 响应提取 token 用量（best-effort）。"""
    usage = data.get('usage', {})
    if fmt == 'anthropic':
        return usage.get('input_tokens', 0), usage.get('output_tokens', 0)
    return usage.get('prompt_tokens', 0), usage.get('completion_tokens', 0)


def _emit_backend_error(backend: str, error_code: int | None, error_text: str) -> None:
    try:
        from observability.metrics import record as _obs_record
        from observability.events import backend_error_event
        from health_tracker import classify_failure
        fc = classify_failure(error_code, error_text)
        _obs_record(backend_error_event("", backend, fc))
    except ImportError:
        pass


def _extract_code(e: Exception) -> Optional[int]:
    """从异常中提取 HTTP 状态码。兼容 httpx 和 urllib。"""
    if isinstance(e, httpx.HTTPStatusError):
        return e.response.status_code
    if isinstance(e, httpx.RequestError):
        return None
    for attr in ('status_code', 'code', 'status'):
        val = getattr(e, attr, None)
        if isinstance(val, int):
            return val
    s = str(e)
    if '429' in s:
        return 429
    if '401' in s:
        return 401
    if '403' in s:
        return 403
    return None


# ── Streaming API Call ────────────────────────────────────────────────────────

def call_api_stream(backend: str, messages: list[dict], max_tokens: int = 4096,
                    *, system_prompt: str = "", ide: str = "") -> Generator[str, None, None]:
    """流式调用后端，yield 文本 chunk。失败抛 BackendError。"""
    cfg = BACKENDS.get(backend)
    if not cfg:
        raise BackendError(f'{backend} unavailable (no key)', status_code=404)
    selected_key, key_provider = _select_key(backend, cfg)
    if not selected_key:
        raise BackendError(f'{backend} unavailable (no key)', status_code=404)
    if health_tracker.is_cooled_down(backend):
        raise BackendError(f'{backend} is cooling down', status_code=503)

    headers = _build_headers(cfg, key=selected_key)
    body = _build_body(cfg, messages, max_tokens, system_prompt, ide, stream=True)
    timeout = cfg.get('timeout', 60)
    fmt = cfg['fmt']
    t0 = time.time()

    try:
        with _build_client(backend, timeout) as client:
            pending_chunks = []
            total_text = ""
            flushed = False

            with client.stream("POST", cfg['url'], content=body, headers=headers) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line or not line.startswith('data: '):
                        continue
                    data_str = line[6:]
                    if data_str == '[DONE]':
                        break
                    text = _parse_sse_chunk(data_str, fmt)
                    if text:
                        total_text += text
                        if flushed:
                            yield _clean_brand_only(text, backend)
                        else:
                            pending_chunks.append(text)
                            if len(total_text) > 200:
                                if _is_backend_error(total_text):
                                    health_tracker.record_failure(
                                        backend, error_code=429,
                                        error_text=total_text)
                                    raise BackendError(
                                        f'{backend} error: {total_text[:60]}',
                                        status_code=429)
                                buffered = "".join(pending_chunks)
                                cleaned = clean_response(buffered, backend)
                                if cleaned:
                                    yield cleaned
                                pending_chunks = []
                                flushed = True

        if not flushed:
            if not total_text:
                health_tracker.record_failure(
                    backend, error_code=502, error_text="empty stream")
                raise BackendError(f'{backend} returned empty stream', status_code=502)
            if _is_backend_error(total_text):
                health_tracker.record_failure(
                    backend, error_code=429, error_text=total_text)
                raise BackendError(
                    f'{backend} returned error: {total_text[:60]}',
                    status_code=429)
            for pc in pending_chunks:
                cleaned = clean_response(pc, backend)
                if cleaned:
                    yield cleaned

        latency_ms = int((time.time() - t0) * 1000)
        health_tracker.record_success(backend, latency_ms)
        _report_key_result(key_provider, selected_key, True)
        health_tracker.record_response_quality(
            backend, len(total_text) if total_text else 0)

    except BackendError as e:
        _report_key_result(
            key_provider, selected_key, False,
            error_code=e.status_code or 0, retry_after=0)
        raise
    except httpx.HTTPStatusError as e:
        error_code = e.response.status_code
        health_tracker.record_failure(
            backend, error_code=error_code, error_text=str(e))
        _report_key_result(
            key_provider, selected_key, False,
            error_code=error_code, retry_after=_extract_retry_after(e))
        raise BackendError(str(e), status_code=error_code) from e
    except Exception as e:
        error_code = _extract_code(e)
        health_tracker.record_failure(
            backend, error_code=error_code, error_text=str(e))
        _report_key_result(
            key_provider, selected_key, False,
            error_code=error_code or 0, retry_after=_extract_retry_after(e))
        if DEBUG:
            print(f'[STREAM] {backend} error: {e}', file=sys.stderr)
        raise BackendError(str(e), status_code=error_code) from e


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


# ── Async API Calls ─────────────────────────────────────────────────────────

async def call_api_async(backend: str, messages: list[dict],
                          max_tokens: int = 4096,
                          *, system_prompt: str = "", ide: str = "") -> str:
    """Async equivalent of call_api. Uses httpx.AsyncClient."""
    cfg = BACKENDS.get(backend)
    if not cfg:
        raise BackendError(f'{backend} unavailable (no key)', status_code=404)
    selected_key, key_provider = _select_key(backend, cfg)
    if not selected_key:
        raise BackendError(f'{backend} unavailable (no key)', status_code=404)

    if health_tracker.is_cooled_down(backend):
        raise BackendError(f'{backend} is cooled down', status_code=503)

    t0 = time.time()
    headers = _build_headers(cfg, key=selected_key)
    body = _build_body(cfg, messages, max_tokens, system_prompt, ide)
    timeout = cfg.get('timeout', 60)

    try:
        async with _build_async_client(backend, timeout) as client:
            resp = await client.post(cfg['url'], content=body, headers=headers)
            resp.raise_for_status()
            d = resp.json()

        answer = _extract_answer(d, cfg['fmt'])

        if _is_backend_error(answer):
            health_tracker.record_failure(
                backend, error_code=429, error_text=answer)
            raise BackendError(
                f'{backend} returned error response: {answer[:60]}',
                status_code=429)

        latency_ms = int((time.time() - t0) * 1000)
        health_tracker.record_success(backend, latency_ms)
        _report_key_result(key_provider, selected_key, True)
        cleaned = clean_response(answer, backend)
        health_tracker.record_response_quality(
            backend, len(cleaned) if cleaned else 0)

        p_tok, c_tok = _extract_usage(d, cfg['fmt'])
        try:
            import budget_manager
            budget_manager.record_token_usage(backend, p_tok, c_tok)
        except ImportError:
            pass

        return cleaned

    except BackendError as e:
        _report_key_result(key_provider, selected_key, False,
                           error_code=e.status_code or 0, retry_after=0)
        raise
    except httpx.HTTPStatusError as e:
        error_code = e.response.status_code
        health_tracker.record_failure(
            backend, error_code=error_code, error_text=str(e))
        _report_key_result(key_provider, selected_key, False,
                           error_code=error_code,
                           retry_after=_extract_retry_after(e))
        raise BackendError(str(e), status_code=error_code) from e
    except Exception as e:
        error_code = _extract_code(e)
        health_tracker.record_failure(
            backend, error_code=error_code, error_text=str(e))
        _report_key_result(key_provider, selected_key, False,
                           error_code=error_code or 0,
                           retry_after=_extract_retry_after(e))
        if DEBUG:
            print(f'[HTTP] {backend} async error: {e}', file=sys.stderr)
        raise BackendError(str(e), status_code=error_code) from e


async def call_api_stream_async(backend: str, messages: list[dict],
                                 max_tokens: int = 4096,
                                 *, system_prompt: str = "",
                                 ide: str = "") -> AsyncIterator[str]:
    """Async SSE streaming. No threads, no queues."""
    cfg = BACKENDS.get(backend)
    if not cfg:
        raise BackendError(f'{backend} unavailable (no key)', status_code=404)
    selected_key, key_provider = _select_key(backend, cfg)
    if not selected_key:
        raise BackendError(f'{backend} unavailable (no key)', status_code=404)
    if health_tracker.is_cooled_down(backend):
        raise BackendError(f'{backend} is cooling down', status_code=503)

    headers = _build_headers(cfg, key=selected_key)
    body = _build_body(cfg, messages, max_tokens, system_prompt, ide, stream=True)
    timeout = cfg.get('timeout', 60)
    fmt = cfg['fmt']
    t0 = time.time()

    try:
        async with _build_async_client(backend, timeout) as client:
            pending_chunks = []
            total_text = ""
            flushed = False

            async with client.stream("POST", cfg['url'], content=body,
                                      headers=headers) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line or not line.startswith('data: '):
                        continue
                    data_str = line[6:]
                    if data_str == '[DONE]':
                        break
                    text = _parse_sse_chunk(data_str, fmt)
                    if text:
                        total_text += text
                        if flushed:
                            yield _clean_brand_only(text, backend)
                        else:
                            pending_chunks.append(text)
                            if len(total_text) > 200:
                                if _is_backend_error(total_text):
                                    health_tracker.record_failure(
                                        backend, error_code=429,
                                        error_text=total_text)
                                    raise BackendError(
                                        f'{backend} error: {total_text[:60]}',
                                        status_code=429)
                                buffered = "".join(pending_chunks)
                                cleaned_out = clean_response(buffered, backend)
                                if cleaned_out:
                                    yield cleaned_out
                                pending_chunks = []
                                flushed = True

        if not flushed:
            if not total_text:
                health_tracker.record_failure(
                    backend, error_code=502, error_text="empty stream")
                raise BackendError(
                    f'{backend} returned empty stream', status_code=502)
            if _is_backend_error(total_text):
                health_tracker.record_failure(
                    backend, error_code=429, error_text=total_text)
                raise BackendError(
                    f'{backend} returned error: {total_text[:60]}',
                    status_code=429)
            for pc in pending_chunks:
                cleaned_out = clean_response(pc, backend)
                if cleaned_out:
                    yield cleaned_out

        latency_ms = int((time.time() - t0) * 1000)
        health_tracker.record_success(backend, latency_ms)
        _report_key_result(key_provider, selected_key, True)
        health_tracker.record_response_quality(
            backend, len(total_text) if total_text else 0)

    except BackendError as e:
        _report_key_result(key_provider, selected_key, False,
                           error_code=e.status_code or 0, retry_after=0)
        raise
    except httpx.HTTPStatusError as e:
        error_code = e.response.status_code
        health_tracker.record_failure(
            backend, error_code=error_code, error_text=str(e))
        _report_key_result(key_provider, selected_key, False,
                           error_code=error_code,
                           retry_after=_extract_retry_after(e))
        raise BackendError(str(e), status_code=error_code) from e
    except Exception as e:
        error_code = _extract_code(e)
        health_tracker.record_failure(
            backend, error_code=error_code, error_text=str(e))
        _report_key_result(key_provider, selected_key, False,
                           error_code=error_code or 0,
                           retry_after=_extract_retry_after(e))
        if DEBUG:
            print(f'[STREAM] {backend} async error: {e}', file=sys.stderr)
        raise BackendError(str(e), status_code=error_code) from e


async def call_raw_async(backend: str, payload: bytes) -> dict:
    """Async equivalent of call_raw."""
    cfg = BACKENDS.get(backend)
    if not cfg:
        raise BackendError(f'{backend} unavailable', status_code=404)
    selected_key, key_provider = _select_key(backend, cfg)
    if not selected_key:
        raise BackendError(f'{backend} unavailable', status_code=404)
    t0 = time.time()
    headers = {'Content-Type': 'application/json',
               'Authorization': f"Bearer {selected_key}"}
    try:
        async with _build_async_client(backend, cfg.get('timeout', 30)) as client:
            resp = await client.post(cfg['url'], content=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        latency_ms = int((time.time() - t0) * 1000)
        health_tracker.record_success(backend, latency_ms)
        _report_key_result(key_provider, selected_key, True)
        return data
    except BackendError as e:
        _report_key_result(key_provider, selected_key, False,
                           error_code=e.status_code or 0, retry_after=0)
        raise
    except httpx.HTTPStatusError as e:
        error_code = e.response.status_code
        health_tracker.record_failure(
            backend, error_code=error_code, error_text=str(e))
        _report_key_result(key_provider, selected_key, False,
                           error_code=error_code,
                           retry_after=_extract_retry_after(e))
        raise BackendError(str(e), status_code=error_code) from e
    except Exception as e:
        error_code = _extract_code(e)
        health_tracker.record_failure(
            backend, error_code=error_code, error_text=str(e))
        _report_key_result(key_provider, selected_key, False,
                           error_code=error_code or 0,
                           retry_after=_extract_retry_after(e))
        raise BackendError(str(e), status_code=error_code) from e
