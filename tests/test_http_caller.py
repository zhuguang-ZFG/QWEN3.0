"""Tests for http_caller.py — httpx migration."""
import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest

import http_caller
import key_pool
from backends import BACKENDS
from http_caller import (
    BackendError,
    _build_body,
    _build_client,
    _build_headers,
    _extract_answer,
    _extract_code,
    _parse_sse_chunk,
    call_api,
    clean_response,
)


def _mock_httpx_client(json_data=None, status_code=200):
    """Build a mock httpx.Client that returns given JSON."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.json.return_value = json_data or {}
    mock_resp.raise_for_status.return_value = None
    mock_resp.status_code = status_code
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False
    mock_client.post.return_value = mock_resp
    return mock_client


def _mock_httpx_stream_client(lines):
    """Build a mock httpx.Client that yields SSE lines."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.iter_lines.return_value = iter(lines)
    mock_stream = MagicMock()
    mock_stream.__enter__.return_value = mock_resp
    mock_stream.__exit__.return_value = False
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False
    mock_client.stream.return_value = mock_stream
    return mock_client


class _MockAsyncHttpxClient:
    def __init__(self, json_data=None):
        self.response = MagicMock()
        self.response.json.return_value = json_data or {}
        self.response.raise_for_status.return_value = None
        self.post_calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, *args, **kwargs):
        self.post_calls.append((args, kwargs))
        return self.response


class _MockAsyncStreamResponse:
    def __init__(self, lines):
        self._lines = lines

    def raise_for_status(self):
        return None

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class _MockAsyncStreamContext:
    def __init__(self, lines):
        self.response = _MockAsyncStreamResponse(lines)

    async def __aenter__(self):
        return self.response

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _MockAsyncStreamClient(_MockAsyncHttpxClient):
    def __init__(self, lines):
        super().__init__()
        self._lines = lines

    def stream(self, *args, **kwargs):
        return _MockAsyncStreamContext(self._lines)


async def _collect_async(async_iterable):
    return [chunk async for chunk in async_iterable]


# ── _build_headers ────────────────────────────────────────────────────────────

def test_build_headers_anthropic_xapikey():
    cfg = {'fmt': 'anthropic', 'key': 'sk-test', 'auth': 'x-api-key'}
    h = _build_headers(cfg)
    assert h['x-api-key'] == 'sk-test'
    assert 'Authorization' not in h
    assert h['anthropic-version'] == '2023-06-01'


def test_build_headers_anthropic_bearer():
    cfg = {'fmt': 'anthropic', 'key': 'sk-test', 'auth': 'bearer'}
    h = _build_headers(cfg)
    assert h['Authorization'] == 'Bearer sk-test'
    assert 'x-api-key' not in h


def test_build_headers_openai():
    cfg = {'fmt': 'openai', 'key': 'sk-test'}
    h = _build_headers(cfg)
    assert h['Authorization'] == 'Bearer sk-test'
    assert h['User-Agent'] == 'LiMa/2.0'


def test_build_headers_can_use_selected_pool_key_without_mutating_config():
    cfg = {'fmt': 'openai', 'key': 'sk-primary'}
    h = _build_headers(cfg, key='sk-pooled')
    assert h['Authorization'] == 'Bearer sk-pooled'
    assert cfg['key'] == 'sk-primary'


# ── _build_body ───────────────────────────────────────────────────────────────

def test_build_body_openai_basic():
    cfg = {'fmt': 'openai', 'model': 'gpt-4', 'key': 'k'}
    msgs = [{'role': 'user', 'content': 'hello'}]
    raw = _build_body(cfg, msgs, 1024, system_prompt='You are helpful.')
    body = json.loads(raw)
    assert body['model'] == 'gpt-4'
    assert body['max_tokens'] == 1024
    assert body['messages'][0]['role'] == 'system'
    assert 'You are helpful.' in body['messages'][0]['content']
    # Message may have providerOptions injected by OpenCode modules
    assert body['messages'][1]['role'] == msgs[0]['role']
    assert body['messages'][1]['content'] == msgs[0]['content']


def test_build_body_openai_no_system_omits_system_message():
    cfg = {'fmt': 'openai', 'model': 'gpt-4o-mini', 'key': 'none', 'no_system': True}
    msgs = [{'role': 'user', 'content': 'hello'}]
    raw = _build_body(cfg, msgs, 256)
    body = json.loads(raw)
    # Check core fields, ignore providerOptions if present
    assert len(body['messages']) == len(msgs)
    assert body['messages'][0]['role'] == msgs[0]['role']
    # Content may include model optimization instructions
    assert 'hello' in body['messages'][0]['content']
    assert all(m['role'] != 'system' for m in body['messages'])


def test_build_body_openai_no_system_merges_prompt_into_first_user_message():
    cfg = {'fmt': 'openai', 'model': 'gpt-4o-mini', 'key': 'none', 'no_system': True}
    msgs = [{'role': 'user', 'content': 'hello'}]
    raw = _build_body(cfg, msgs, 256, system_prompt='Base.', ide='OpenCode')
    body = json.loads(raw)
    assert body['messages'][0]['role'] == 'user'
    assert 'Base.' in body['messages'][0]['content']
    assert 'OpenCode' in body['messages'][0]['content']
    assert 'hello' in body['messages'][0]['content']
    assert all(m['role'] != 'system' for m in body['messages'])


def test_build_body_anthropic_with_system():
    cfg = {'fmt': 'anthropic', 'model': 'claude-3', 'key': 'k'}
    msgs = [{'role': 'user', 'content': 'hi'}]
    raw = _build_body(cfg, msgs, 2048, system_prompt='Be concise.')
    body = json.loads(raw)
    # System prompt may be enhanced with additional instructions
    assert 'Be concise.' in body['system']
    # Check core fields, ignore providerOptions if present
    assert len(body['messages']) == len(msgs)
    assert body['messages'][0]['role'] == msgs[0]['role']
    assert body['messages'][0]['content'] == msgs[0]['content']


def test_build_body_anthropic_no_system():
    cfg = {'fmt': 'anthropic', 'model': 'omni', 'key': 'k', 'no_system': True}
    msgs = [{'role': 'user', 'content': 'hello'}]
    raw = _build_body(cfg, msgs, 1024)
    body = json.loads(raw)
    assert 'system' not in body
    assert body['messages'][0]['content'] == [{'type': 'text', 'text': 'hello'}]


def test_build_body_stream_flag():
    cfg = {'fmt': 'openai', 'model': 'gpt-4', 'key': 'k'}
    msgs = [{'role': 'user', 'content': 'hi'}]
    raw = _build_body(cfg, msgs, 1024, stream=True)
    body = json.loads(raw)
    assert body['stream'] is True


def test_build_body_explicit_sampling_overrides_model_defaults():
    cfg = {'fmt': 'openai', 'model': 'qwen-plus', 'key': 'k'}
    msgs = [{'role': 'user', 'content': 'hi'}]
    raw = _build_body(
        cfg,
        msgs,
        1024,
        backend_name='qwen',
        sampling={'temperature': 0.2, 'top_p': 0.7},
    )
    body = json.loads(raw)
    assert body['temperature'] == 0.2
    assert body['top_p'] == 0.7


def test_build_body_can_force_explicit_non_stream_flag():
    cfg = {'fmt': 'openai', 'model': 'mimo-web', 'key': 'none', 'force_stream_param': True}
    msgs = [{'role': 'user', 'content': 'hi'}]
    raw = _build_body(cfg, msgs, 1024, stream=False)
    body = json.loads(raw)
    assert body['stream'] is False


def test_default_streaming_web_proxies_force_non_stream_flag():
    for name in ('longcat_web', 'longcat_web_think', 'longcat_web_research',
                 'mimo_web', 'mimo_web_think', 'mimo_web_flash'):
        assert BACKENDS[name]['force_stream_param'] is True


# ── _extract_answer ───────────────────────────────────────────────────────────

def test_extract_answer_openai():
    assert _extract_answer(
        {'choices': [{'message': {'content': 'hello world'}}]}, 'openai') == 'hello world'


def test_extract_answer_openai_reasoning_fallback():
    assert _extract_answer(
        {'choices': [{'message': {'content': None, 'reasoning_content': 'think'}}]},
        'openai') == 'think'


def test_extract_answer_anthropic():
    assert _extract_answer(
        {'content': [{'type': 'text', 'text': 'bonjour'}]}, 'anthropic') == 'bonjour'


def test_extract_answer_anthropic_thinking():
    assert _extract_answer(
        {'content': [{'type': 'thinking', 'thinking': 'let me think'}]},
        'anthropic') == 'let me think'


# ── _extract_code ─────────────────────────────────────────────────────────────

def test_extract_code_from_attr():
    e = Exception("fail")
    e.status_code = 429
    assert _extract_code(e) == 429


def test_extract_code_from_string():
    assert _extract_code(Exception("HTTP Error 401: Unauthorized")) == 401


def test_extract_code_none():
    assert _extract_code(Exception("random error")) is None


def test_extract_code_httpx_status_error():
    import httpx
    mock_resp = MagicMock()
    mock_resp.status_code = 503
    e = httpx.HTTPStatusError("server error", request=MagicMock(), response=mock_resp)
    assert _extract_code(e) == 503


# ── _parse_sse_chunk ──────────────────────────────────────────────────────────

def test_parse_sse_openai():
    assert _parse_sse_chunk(
        json.dumps({'choices': [{'delta': {'content': 'hi'}}]}), 'openai') == 'hi'


def test_parse_sse_anthropic():
    data = json.dumps({
        'type': 'content_block_delta',
        'delta': {'type': 'text_delta', 'text': 'hey'},
    })
    assert _parse_sse_chunk(data, 'anthropic') == 'hey'


def test_parse_sse_invalid_json():
    assert _parse_sse_chunk('not json', 'openai') == ''


# ── clean_response ────────────────────────────────────────────────────────────

def test_clean_response_hides_model_names():
    result = clean_response("I am Claude, made by Anthropic.")
    assert 'Claude' not in result
    assert 'Anthropic' not in result


def test_clean_response_empty():
    assert clean_response('') == ''
    assert clean_response('[ERR] something') == ''


def test_clean_response_treats_web_proxy_control_errors_as_backend_errors():
    assert clean_response('[MiMo Cookie expired]') == ''
    assert clean_response('[MiMo HTTP 401]') == ''
    assert clean_response('[LongCat Cookie expired]') == ''
    assert clean_response('[LongCat HTTP 502]') == ''


def test_clean_response_chinese_identity():
    result = clean_response("我是由DeepSeek开发的AI助手")
    assert 'DeepSeek' not in result


# ── _build_client ─────────────────────────────────────────────────────────────

def test_build_client_gfw_backend():
    client = _build_client('google_flash', 30)
    assert client is not None
    client.close()


def test_build_client_normal_backend():
    client = _build_client('longcat_chat', 30)
    assert client is not None
    client.close()


# ── call_api (mocked) ─────────────────────────────────────────────────────────

@patch('http_caller.health_tracker')
@patch('http_caller._get_client')
def test_call_api_success_openai(mock_get_client, mock_ht):
    mock_ht.is_cooled_down.return_value = False
    mock_get_client.return_value = _mock_httpx_client({
        'choices': [{'message': {'content': 'hello world'}}],
    })

    with patch.dict(http_caller.BACKENDS, {
        'test_backend': {'url': 'http://test.com/v1/chat/completions',
                        'key': 'sk-test', 'model': 'test-model',
                        'fmt': 'openai', 'timeout': 10}
    }):
        result = call_api('test_backend', [{'role': 'user', 'content': 'hi'}],
                          system_prompt='Be helpful.')
    assert 'hello world' in result
    mock_ht.record_success.assert_called_once()


@patch('http_caller.key_pool.is_exhausted')
@patch('http_caller.key_pool.ensure_env_pool')
@patch('http_caller.key_pool.report_key_result')
@patch('http_caller.key_pool.get_key')
@patch('http_caller.health_tracker')
@patch('http_caller._get_client')
def test_call_api_uses_key_pool_key_and_reports_success(
    mock_get_client, mock_ht, mock_get_key, mock_report_key_result,
    mock_ensure_env_pool, mock_is_exhausted,
):
    mock_ht.is_cooled_down.return_value = False
    mock_ensure_env_pool.return_value = True
    mock_is_exhausted.return_value = False
    mock_get_key.return_value = 'sk-pooled'
    mock_get_client.return_value = _mock_httpx_client({
        'choices': [{'message': {'content': 'hello world'}}],
    })

    with patch.dict(http_caller.BACKENDS, {
        'pool_backend': {'url': 'http://test.com/v1/chat/completions',
                         'key': 'sk-primary', 'key_pool': 'unit-provider',
                         'model': 'test-model', 'fmt': 'openai', 'timeout': 10}
    }):
        result = call_api('pool_backend', [{'role': 'user', 'content': 'hi'}])

    req_headers = mock_get_client.return_value.post.call_args[1]['headers']
    assert req_headers['Authorization'] == 'Bearer sk-pooled'
    assert 'hello world' in result
    mock_report_key_result.assert_called_once_with('unit-provider', 'sk-pooled', True)


@patch('http_caller.key_pool.is_exhausted')
@patch('http_caller.key_pool.ensure_env_pool')
@patch('http_caller.key_pool.report_key_result')
@patch('http_caller.key_pool.get_key')
@patch('http_caller.health_tracker')
@patch('http_caller._get_client')
def test_call_api_reports_key_pool_failure_with_retry_after(
    mock_get_client, mock_ht, mock_get_key, mock_report_key_result,
    mock_ensure_env_pool, mock_is_exhausted,
):
    import httpx
    mock_ht.is_cooled_down.return_value = False
    mock_ensure_env_pool.return_value = True
    mock_is_exhausted.return_value = False
    mock_get_key.return_value = 'sk-pooled'

    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.headers = {'Retry-After': '7'}
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False
    mock_client.post.side_effect = httpx.HTTPStatusError(
        "rate limited", request=MagicMock(), response=mock_resp)
    mock_get_client.return_value = mock_client

    with patch.dict(http_caller.BACKENDS, {
        'pool_backend': {'url': 'http://test.com/v1/chat/completions',
                         'key': 'sk-primary', 'key_pool': 'unit-provider',
                         'model': 'test-model', 'fmt': 'openai', 'timeout': 10}
    }), pytest.raises(BackendError):
        call_api('pool_backend', [{'role': 'user', 'content': 'hi'}])

    mock_report_key_result.assert_called_once_with(
        'unit-provider', 'sk-pooled', False, error_code=429, retry_after=7)


@patch('http_caller.health_tracker')
@patch('http_caller._get_client')
def test_call_api_bootstraps_key_pool_from_provider_env(
    mock_get_client, mock_ht, monkeypatch,
):
    key_pool.clear_pools()
    monkeypatch.setenv('LIMA_KEY_POOL_GROQ', 'sk-env-1,sk-env-2:2')
    mock_ht.is_cooled_down.return_value = False
    mock_get_client.return_value = _mock_httpx_client({
        'choices': [{'message': {'content': 'hello world'}}],
    })

    with patch.dict(http_caller.BACKENDS, {
        'groq_unit': {'url': 'https://api.groq.com/openai/v1/chat/completions',
                      'key': 'sk-primary', 'model': 'test-model',
                      'fmt': 'openai', 'timeout': 10}
    }):
        call_api('groq_unit', [{'role': 'user', 'content': 'hi'}])

    req_headers = mock_get_client.return_value.post.call_args[1]['headers']
    assert req_headers['Authorization'] in {'Bearer sk-env-1', 'Bearer sk-env-2'}
    key_pool.clear_pools()


@patch('http_caller.health_tracker')
def test_call_api_cooled_down(mock_ht):
    mock_ht.is_cooled_down.return_value = True
    with patch.dict(http_caller.BACKENDS, {'any_backend': {
        'url': 'http://x', 'key': 'sk-test', 'model': 'm', 'fmt': 'openai'
    }}), pytest.raises(BackendError) as exc_info:
        call_api('any_backend', [{'role': 'user', 'content': 'hi'}])
    assert exc_info.value.status_code == 503


@patch('http_caller.health_tracker')
def test_call_api_no_key(mock_ht):
    mock_ht.is_cooled_down.return_value = False
    with patch.dict(http_caller.BACKENDS, {
        'nokey': {'url': 'http://x', 'key': '', 'model': 'm', 'fmt': 'openai'}
    }), pytest.raises(BackendError) as exc_info:
        call_api('nokey', [{'role': 'user', 'content': 'hi'}])
    assert exc_info.value.status_code == 404


@patch('http_caller.health_tracker')
@patch('http_caller._get_client')
def test_call_api_network_error(mock_get_client, mock_ht):
    mock_ht.is_cooled_down.return_value = False
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False
    mock_client.post.side_effect = Exception("Connection refused")
    mock_get_client.return_value = mock_client

    with patch.dict(http_caller.BACKENDS, {
        'fail_backend': {'url': 'http://fail.com/v1', 'key': 'sk-x',
                        'model': 'm', 'fmt': 'openai', 'timeout': 5}
    }), pytest.raises(BackendError):
        call_api('fail_backend', [{'role': 'user', 'content': 'hi'}])
    mock_ht.record_failure.assert_called_once()


@patch('http_caller.health_tracker')
@patch('http_caller._get_client')
def test_call_api_backend_error_emits_observability(mock_get_client, mock_ht):
    from observability.metrics import get_metrics_snapshot, reset_metrics

    reset_metrics()
    mock_ht.is_cooled_down.return_value = False
    mock_get_client.return_value = _mock_httpx_client({
        'choices': [{'message': {'content': 'rate limit'}}],
    })

    with patch.dict(http_caller.BACKENDS, {
        'err_backend': {'url': 'http://test.com/v1/chat/completions',
                        'key': 'sk-test', 'model': 'test-model',
                        'fmt': 'openai', 'timeout': 10}
    }), pytest.raises(BackendError) as exc_info:
        call_api('err_backend', [{'role': 'user', 'content': 'hi'}])

    snapshot = get_metrics_snapshot()
    assert exc_info.value.status_code == 429
    assert snapshot["event_type_counts"]["backend_error"] == 1
    assert snapshot["backends"]["err_backend"]["failure"] == 1
    reset_metrics()


@patch('http_caller.health_tracker')
@patch('http_caller._get_async_client')
def test_call_api_async_success_openai(mock_get_async_client, mock_ht):
    mock_ht.is_cooled_down.return_value = False
    mock_get_async_client.return_value = _MockAsyncHttpxClient({
        'choices': [{'message': {'content': 'hello async'}}],
    })

    with patch.dict(http_caller.BACKENDS, {
        'async_backend': {'url': 'http://test.com/v1/chat/completions',
                          'key': 'sk-test', 'model': 'test-model',
                          'fmt': 'openai', 'timeout': 10}
    }):
        result = asyncio.run(http_caller.call_api_async(
            'async_backend', [{'role': 'user', 'content': 'hi'}]))

    assert 'hello async' in result
    mock_ht.record_success.assert_called_once()


@patch('http_caller.health_tracker')
@patch('http_caller._build_async_client')
def test_call_raw_async_success(mock_build_async_client, mock_ht):
    mock_build_async_client.return_value = _MockAsyncHttpxClient({'ok': True})

    with patch.dict(http_caller.BACKENDS, {
        'async_raw': {'url': 'http://test.com/v1/chat/completions',
                      'key': 'sk-test', 'model': 'test-model',
                      'fmt': 'openai', 'timeout': 10}
    }):
        result = asyncio.run(http_caller.call_raw_async('async_raw', b'{}'))

    assert result == {'ok': True}
    mock_ht.record_success.assert_called_once()


@patch('http_caller.health_tracker')
@patch('http_caller._get_async_client')
def test_call_api_stream_async_success_openai(mock_get_async_client, mock_ht):
    mock_ht.is_cooled_down.return_value = False
    line = 'data: ' + json.dumps({'choices': [{'delta': {'content': 'hello stream'}}]})
    mock_get_async_client.return_value = _MockAsyncStreamClient([line, 'data: [DONE]'])

    with patch.dict(http_caller.BACKENDS, {
        'async_stream': {'url': 'http://test.com/v1/chat/completions',
                         'key': 'sk-test', 'model': 'test-model',
                         'fmt': 'openai', 'timeout': 10}
    }):
        chunks = asyncio.run(_collect_async(http_caller.call_api_stream_async(
            'async_stream', [{'role': 'user', 'content': 'hi'}])))

    assert ''.join(chunks) == 'hello stream'
    mock_ht.record_success.assert_called_once()


# ── Token extraction ───────────────────────────────────────────────────────────

def test_extract_usage_openai():
    from http_caller import _extract_usage
    data = {
        'choices': [{'message': {'content': 'hello'}}],
        'usage': {'prompt_tokens': 150, 'completion_tokens': 50, 'total_tokens': 200},
    }
    p, c = _extract_usage(data, 'openai')
    assert p == 150
    assert c == 50


def test_extract_usage_anthropic():
    from http_caller import _extract_usage
    data = {
        'content': [{'type': 'text', 'text': 'hi'}],
        'usage': {'input_tokens': 100, 'output_tokens': 30},
    }
    p, c = _extract_usage(data, 'anthropic')
    assert p == 100
    assert c == 30


def test_extract_usage_no_usage_field():
    from http_caller import _extract_usage
    p, c = _extract_usage({'choices': [{'message': {'content': 'hi'}}]}, 'openai')
    assert p == 0
    assert c == 0


# ── Token telemetry in call_api ───────────────────────────────────────────────

@patch('http_caller.health_tracker')
@patch('http_caller._get_client')
def test_call_api_records_token_usage(mock_get_client, mock_ht):
    mock_ht.is_cooled_down.return_value = False
    mock_get_client.return_value = _mock_httpx_client({
        'choices': [{'message': {'content': 'hello world'}}],
        'usage': {'prompt_tokens': 200, 'completion_tokens': 80, 'total_tokens': 280},
    })

    import budget_manager
    budget_manager.reset_for_tests()

    with patch.dict(http_caller.BACKENDS, {
        'test_tok': {'url': 'http://test.com/v1/chat/completions',
                    'key': 'sk-test', 'model': 'test-model', 'fmt': 'openai', 'timeout': 10}
    }):
        call_api('test_tok', [{'role': 'user', 'content': 'hi'}])

    usage = budget_manager.get_token_usage('test_tok')
    assert usage['prompt'] == 200
    assert usage['completion'] == 80
    assert usage['requests'] == 1
    budget_manager.reset_for_tests()


# ── Key pool exhaustion ────────────────────────────────────────────────────────

@patch('http_caller.key_pool.ensure_env_pool')
@patch('http_caller.key_pool.is_exhausted')
@patch('http_caller.health_tracker')
def test_call_api_key_pool_exhausted_returns_empty_key(mock_ht, mock_exhausted, mock_ensure):
    mock_ht.is_cooled_down.return_value = False
    mock_ensure.return_value = True
    mock_exhausted.return_value = True

    with patch.dict(http_caller.BACKENDS, {
        'pooled': {'url': 'http://test.com/v1', 'key': 'sk-default',
                   'model': 'm', 'fmt': 'openai', 'key_pool': 'exhausted_provider'}
    }), pytest.raises(BackendError) as exc_info:
        call_api('pooled', [{'role': 'user', 'content': 'hi'}])
    assert exc_info.value.status_code == 404
    mock_exhausted.assert_called_once_with('exhausted_provider')


@patch('http_caller.key_pool.is_exhausted')
@patch('http_caller.key_pool.ensure_env_pool')
def test_select_key_falls_back_to_backend_key_when_pool_not_configured(
    mock_ensure_env_pool, mock_is_exhausted,
):
    mock_ensure_env_pool.return_value = False

    key, provider = http_caller._select_key(
        'github_gpt4o',
        {'key': 'sk-static', 'fmt': 'openai'},
    )

    assert key == 'sk-static'
    assert provider == 'github'
    mock_is_exhausted.assert_not_called()


@patch('http_caller.key_pool.is_exhausted')
@patch('http_caller.key_pool.ensure_env_pool')
@patch('http_caller.key_pool.report_key_result')
@patch('http_caller.key_pool.get_key')
@patch('http_caller.health_tracker')
@patch('http_caller._get_client')
def test_call_api_stream_reports_empty_stream_as_502_to_key_pool(
    mock_get_client, mock_ht, mock_get_key, mock_report_key_result,
    mock_ensure_env_pool, mock_is_exhausted,
):
    mock_ht.is_cooled_down.return_value = False
    mock_ensure_env_pool.return_value = True
    mock_is_exhausted.return_value = False
    mock_get_key.return_value = 'sk-pooled'
    mock_get_client.return_value = _mock_httpx_stream_client(['data: [DONE]'])

    with patch.dict(http_caller.BACKENDS, {
        'pool_backend': {'url': 'http://test.com/v1/chat/completions',
                         'key': 'sk-primary', 'key_pool': 'unit-provider',
                         'model': 'test-model', 'fmt': 'openai', 'timeout': 10}
    }), pytest.raises(BackendError) as exc_info:
        list(http_caller.call_api_stream(
            'pool_backend', [{'role': 'user', 'content': 'hi'}]))

    assert exc_info.value.status_code == 502
    mock_report_key_result.assert_called_once_with(
        'unit-provider', 'sk-pooled', False, error_code=502, retry_after=0)


# ── Failure classification ────────────────────────────────────────────────────

def test_classify_failure_auth():
    from health_tracker import classify_failure
    assert classify_failure(401) == 'auth_expired'
    assert classify_failure(403) == 'auth_expired'
    assert classify_failure(None, 'unauthorized request') == 'auth_expired'


def test_classify_failure_rate_limit():
    from health_tracker import classify_failure
    assert classify_failure(429) == 'rate_limited'
    assert classify_failure(None, 'too many requests') == 'rate_limited'


def test_classify_failure_quota():
    from health_tracker import classify_failure
    assert classify_failure(None, 'quota exceeded') == 'quota_exhausted'
    assert classify_failure(None, 'insufficient_quota') == 'quota_exhausted'


def test_classify_failure_network():
    from health_tracker import classify_failure
    assert classify_failure(None, 'connection refused') == 'network_error'
    assert classify_failure(None, 'connection reset') == 'network_error'
    assert classify_failure(None, 'connection timed out') == 'network_error'
    assert classify_failure(None, 'read timed out') == 'network_error'
    assert classify_failure(502) == 'network_error'
    assert classify_failure(503) == 'network_error'


def test_classify_failure_timeout():
    from health_tracker import classify_failure
    assert classify_failure(None, 'request timeout after 30s') == 'timeout'


def test_classify_failure_malformed():
    from health_tracker import classify_failure
    assert classify_failure(400) == 'malformed_response'
    assert classify_failure(None, 'JSONDecodeError at line 1') == 'malformed_response'


def test_classify_failure_provider_error():
    from health_tracker import classify_failure
    assert classify_failure(500) == 'provider_error'


def test_classify_failure_anonymous_exhausted():
    from health_tracker import classify_failure
    assert classify_failure(None, 'chat.anonymous_usage_exceeded') == 'manual_refresh_required'
