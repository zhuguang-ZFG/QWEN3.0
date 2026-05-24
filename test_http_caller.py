"""Tests for http_caller.py — Phase 1 of V3 migration."""
import json
import pytest
from unittest.mock import patch, MagicMock

import http_caller
import key_pool
from backends import BACKENDS
from http_caller import (
    BackendError, call_api,
    clean_response, _build_headers, _build_body,
    _extract_answer, _extract_code, _parse_sse_chunk, _get_opener,
)


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
    assert body['messages'][1] == msgs[0]


def test_build_body_openai_no_system_omits_system_message():
    cfg = {
        'fmt': 'openai', 'model': 'gpt-4o-mini',
        'key': 'none', 'no_system': True,
    }
    msgs = [{'role': 'user', 'content': 'hello'}]
    raw = _build_body(cfg, msgs, 256)
    body = json.loads(raw)
    assert body['model'] == 'gpt-4o-mini'
    assert body['max_tokens'] == 256
    assert body['messages'] == msgs
    assert all(m['role'] != 'system' for m in body['messages'])


def test_build_body_openai_no_system_merges_prompt_into_first_user_message():
    cfg = {
        'fmt': 'openai', 'model': 'gpt-4o-mini',
        'key': 'none', 'no_system': True,
    }
    msgs = [{'role': 'user', 'content': 'hello'}]
    raw = _build_body(cfg, msgs, 256, system_prompt='Base.', ide='Cursor')
    body = json.loads(raw)
    assert body['messages'][0]['role'] == 'user'
    assert 'Base.' in body['messages'][0]['content']
    assert 'Cursor' in body['messages'][0]['content']
    assert 'hello' in body['messages'][0]['content']
    assert all(m['role'] != 'system' for m in body['messages'])


def test_build_body_anthropic_with_system():
    cfg = {'fmt': 'anthropic', 'model': 'claude-3', 'key': 'k'}
    msgs = [{'role': 'user', 'content': 'hi'}]
    raw = _build_body(cfg, msgs, 2048, system_prompt='Be concise.')
    body = json.loads(raw)
    assert body['system'] == 'Be concise.'
    assert body['messages'] == msgs


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


def test_build_body_can_force_explicit_non_stream_flag():
    cfg = {
        'fmt': 'openai',
        'model': 'mimo-web',
        'key': 'none',
        'force_stream_param': True,
    }
    msgs = [{'role': 'user', 'content': 'hi'}]
    raw = _build_body(cfg, msgs, 1024, stream=False)
    body = json.loads(raw)
    assert body['stream'] is False


def test_default_streaming_web_proxies_force_non_stream_flag():
    for name in (
        'longcat_web',
        'longcat_web_think',
        'longcat_web_research',
        'mimo_web',
        'mimo_web_think',
        'mimo_web_flash',
    ):
        assert BACKENDS[name]['force_stream_param'] is True


def test_build_body_ide_env_injection():
    cfg = {'fmt': 'openai', 'model': 'gpt-4', 'key': 'k'}
    msgs = [{'role': 'user', 'content': 'hi'}]
    raw = _build_body(cfg, msgs, 1024, system_prompt='Base.', ide='Cursor')
    body = json.loads(raw)
    assert '环境' in body['messages'][0]['content']
    assert 'Cursor' in body['messages'][0]['content']


# ── _extract_answer ───────────────────────────────────────────────────────────

def test_extract_answer_openai():
    data = {'choices': [{'message': {'content': 'hello world'}}]}
    assert _extract_answer(data, 'openai') == 'hello world'


def test_extract_answer_openai_reasoning_fallback():
    data = {'choices': [{'message': {'content': None, 'reasoning_content': 'think...'}}]}
    assert _extract_answer(data, 'openai') == 'think...'


def test_extract_answer_anthropic():
    data = {'content': [{'type': 'text', 'text': 'bonjour'}]}
    assert _extract_answer(data, 'anthropic') == 'bonjour'


def test_extract_answer_anthropic_thinking():
    data = {'content': [{'type': 'thinking', 'thinking': 'let me think...'}]}
    assert _extract_answer(data, 'anthropic') == 'let me think...'


# ── _extract_code ─────────────────────────────────────────────────────────────

def test_extract_code_from_attr():
    e = Exception("fail")
    e.status_code = 429
    assert _extract_code(e) == 429


def test_extract_code_from_string():
    e = Exception("HTTP Error 401: Unauthorized")
    assert _extract_code(e) == 401


def test_extract_code_none():
    e = Exception("random error")
    assert _extract_code(e) is None


# ── _parse_sse_chunk ──────────────────────────────────────────────────────────

def test_parse_sse_openai():
    data = json.dumps({'choices': [{'delta': {'content': 'hi'}}]})
    assert _parse_sse_chunk(data, 'openai') == 'hi'


def test_parse_sse_anthropic():
    data = json.dumps({
        'type': 'content_block_delta',
        'delta': {'type': 'text_delta', 'text': 'hey'}
    })
    assert _parse_sse_chunk(data, 'anthropic') == 'hey'


def test_parse_sse_invalid_json():
    assert _parse_sse_chunk('not json', 'openai') == ''


# ── clean_response ────────────────────────────────────────────────────────────

def test_clean_response_hides_model_names():
    text = "I am Claude, made by Anthropic."
    result = clean_response(text)
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
    text = "我是由DeepSeek开发的AI助手"
    result = clean_response(text)
    assert 'DeepSeek' not in result


# ── _get_opener ───────────────────────────────────────────────────────────────

def test_get_opener_gfw_backend():
    opener = _get_opener('google_flash')
    assert opener is not None


def test_get_opener_normal_backend():
    opener = _get_opener('longcat_chat')
    assert opener is None


# ── call_api (mocked) ─────────────────────────────────────────────────────────

@patch('http_caller.health_tracker')
@patch('urllib.request.urlopen')
def test_call_api_success_openai(mock_urlopen, mock_ht):
    mock_ht.is_cooled_down.return_value = False
    resp_data = json.dumps({
        'choices': [{'message': {'content': 'hello world'}}]
    }).encode()
    mock_resp = MagicMock()
    mock_resp.read.return_value = resp_data
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_urlopen.return_value = mock_resp

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
@patch('urllib.request.urlopen')
def test_call_api_uses_key_pool_key_and_reports_success(
    mock_urlopen, mock_ht, mock_get_key, mock_report_key_result,
    mock_ensure_env_pool, mock_is_exhausted,
):
    mock_ht.is_cooled_down.return_value = False
    mock_ensure_env_pool.return_value = True
    mock_is_exhausted.return_value = False
    mock_get_key.return_value = 'sk-pooled'
    resp_data = json.dumps({
        'choices': [{'message': {'content': 'hello world'}}]
    }).encode()
    mock_resp = MagicMock()
    mock_resp.read.return_value = resp_data
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_urlopen.return_value = mock_resp

    with patch.dict(http_caller.BACKENDS, {
        'pool_backend': {'url': 'http://test.com/v1/chat/completions',
                         'key': 'sk-primary', 'key_pool': 'unit-provider',
                         'model': 'test-model', 'fmt': 'openai',
                         'timeout': 10}
    }):
        result = call_api('pool_backend', [{'role': 'user', 'content': 'hi'}])

    req = mock_urlopen.call_args.args[0]
    assert req.get_header('Authorization') == 'Bearer sk-pooled'
    assert 'hello world' in result
    mock_get_key.assert_called_once_with('unit-provider')
    mock_report_key_result.assert_called_once_with(
        'unit-provider', 'sk-pooled', True)


@patch('http_caller.key_pool.is_exhausted')
@patch('http_caller.key_pool.ensure_env_pool')
@patch('http_caller.key_pool.report_key_result')
@patch('http_caller.key_pool.get_key')
@patch('http_caller.health_tracker')
@patch('urllib.request.urlopen')
def test_call_api_reports_key_pool_failure_with_retry_after(
    mock_urlopen, mock_ht, mock_get_key, mock_report_key_result,
    mock_ensure_env_pool, mock_is_exhausted,
):
    class RateLimited(Exception):
        code = 429
        headers = {'Retry-After': '7'}

    mock_ht.is_cooled_down.return_value = False
    mock_ensure_env_pool.return_value = True
    mock_is_exhausted.return_value = False
    mock_get_key.return_value = 'sk-pooled'
    mock_urlopen.side_effect = RateLimited("rate limited")

    with patch.dict(http_caller.BACKENDS, {
        'pool_backend': {'url': 'http://test.com/v1/chat/completions',
                         'key': 'sk-primary', 'key_pool': 'unit-provider',
                         'model': 'test-model', 'fmt': 'openai',
                         'timeout': 10}
    }):
        with pytest.raises(BackendError):
            call_api('pool_backend', [{'role': 'user', 'content': 'hi'}])

    mock_report_key_result.assert_called_once_with(
        'unit-provider', 'sk-pooled', False, error_code=429, retry_after=7)


@patch('http_caller.health_tracker')
@patch('urllib.request.urlopen')
def test_call_api_bootstraps_key_pool_from_provider_env(
    mock_urlopen, mock_ht, monkeypatch,
):
    key_pool.clear_pools()
    monkeypatch.setenv('LIMA_KEY_POOL_GROQ', 'sk-env-1,sk-env-2:2')
    mock_ht.is_cooled_down.return_value = False
    resp_data = json.dumps({
        'choices': [{'message': {'content': 'hello world'}}]
    }).encode()
    mock_resp = MagicMock()
    mock_resp.read.return_value = resp_data
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_urlopen.return_value = mock_resp

    with patch.dict(http_caller.BACKENDS, {
        'groq_unit': {'url': 'https://api.groq.com/openai/v1/chat/completions',
                      'key': 'sk-primary', 'model': 'test-model',
                      'fmt': 'openai', 'timeout': 10}
    }):
        call_api('groq_unit', [{'role': 'user', 'content': 'hi'}])

    req = mock_urlopen.call_args.args[0]
    assert req.get_header('Authorization') in {
        'Bearer sk-env-1',
        'Bearer sk-env-2',
    }
    key_pool.clear_pools()


@patch('http_caller.health_tracker')
def test_call_api_cooled_down(mock_ht):
    mock_ht.is_cooled_down.return_value = True
    with patch.dict(http_caller.BACKENDS, {'any_backend': {
        'url': 'http://x', 'key': 'sk-test', 'model': 'm', 'fmt': 'openai'
    }}):
        with pytest.raises(BackendError) as exc_info:
            call_api('any_backend', [{'role': 'user', 'content': 'hi'}])
    assert exc_info.value.status_code == 503


@patch('http_caller.health_tracker')
def test_call_api_no_key(mock_ht):
    mock_ht.is_cooled_down.return_value = False
    with patch.dict(http_caller.BACKENDS, {'nokey': {'url': 'http://x', 'key': '', 'model': 'm', 'fmt': 'openai'}}):
        with pytest.raises(BackendError) as exc_info:
            call_api('nokey', [{'role': 'user', 'content': 'hi'}])
    assert exc_info.value.status_code == 404


@patch('http_caller.health_tracker')
@patch('urllib.request.urlopen')
def test_call_api_network_error(mock_urlopen, mock_ht):
    mock_ht.is_cooled_down.return_value = False
    mock_urlopen.side_effect = Exception("Connection refused")

    with patch.dict(http_caller.BACKENDS, {
        'fail_backend': {'url': 'http://fail.com/v1', 'key': 'sk-x',
                         'model': 'm', 'fmt': 'openai', 'timeout': 5}
    }):
        with pytest.raises(BackendError):
            call_api('fail_backend', [{'role': 'user', 'content': 'hi'}])
    mock_ht.record_failure.assert_called_once()


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
    data = {'choices': [{'message': {'content': 'hi'}}]}
    p, c = _extract_usage(data, 'openai')
    assert p == 0
    assert c == 0


# ── Token telemetry in call_api ───────────────────────────────────────────────

@patch('http_caller.health_tracker')
@patch('urllib.request.urlopen')
def test_call_api_records_token_usage(mock_urlopen, mock_ht, monkeypatch):
    mock_ht.is_cooled_down.return_value = False
    resp_data = json.dumps({
        'choices': [{'message': {'content': 'hello world'}}],
        'usage': {'prompt_tokens': 200, 'completion_tokens': 80, 'total_tokens': 280},
    }).encode()
    mock_resp = MagicMock()
    mock_resp.read.return_value = resp_data
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_urlopen.return_value = mock_resp

    import budget_manager
    budget_manager.reset_for_tests()

    with patch.dict(http_caller.BACKENDS, {
        'test_tok': {'url': 'http://test.com/v1/chat/completions',
                     'key': 'sk-test', 'model': 'test-model',
                     'fmt': 'openai', 'timeout': 10}
    }):
        call_api('test_tok', [{'role': 'user', 'content': 'hi'}])

    usage = budget_manager.get_token_usage('test_tok')
    assert usage['prompt'] == 200
    assert usage['completion'] == 80
    assert usage['requests'] == 1
    budget_manager.reset_for_tests()


# ── Key pool exhaustion ────────────────────────────────────────────────────────

@patch('http_caller.key_pool.is_exhausted')
@patch('http_caller.key_pool.ensure_env_pool')
@patch('http_caller.health_tracker')
def test_call_api_key_pool_exhausted_returns_empty_key(
    mock_ht, mock_ensure_env_pool, mock_exhausted,
):
    mock_ht.is_cooled_down.return_value = False
    mock_ensure_env_pool.return_value = True
    mock_exhausted.return_value = True

    with patch.dict(http_caller.BACKENDS, {
        'pooled': {'url': 'http://test.com/v1', 'key': 'sk-default',
                   'model': 'm', 'fmt': 'openai', 'key_pool': 'exhausted_provider'}
    }):
        with pytest.raises(BackendError) as exc_info:
            call_api('pooled', [{'role': 'user', 'content': 'hi'}])
    assert exc_info.value.status_code == 404
    mock_exhausted.assert_called_once_with('exhausted_provider')


@patch('http_caller.key_pool.ensure_env_pool')
def test_select_key_falls_back_to_backend_key_when_pool_not_configured(mock_ensure_env_pool):
    mock_ensure_env_pool.return_value = False

    key, provider = http_caller._select_key(
        'github_gpt4o',
        {'key': 'sk-static', 'fmt': 'openai'},
    )

    assert key == 'sk-static'
    assert provider == 'github'


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
    assert classify_failure(502) == 'network_error'  # 502 is network, not provider


def test_classify_failure_anonymous_exhausted():
    from health_tracker import classify_failure
    assert classify_failure(None, 'chat.anonymous_usage_exceeded') == 'manual_refresh_required'
