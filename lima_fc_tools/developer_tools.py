"""Telegram Function Calling tools."""

import base64
import hashlib
import json
import re
import time

import httpx

from .http_client import _get
from .registry import tool


@tool('get_domain_info', 'Run the get_domain_info utility.', {'properties': {'domain': {'description': 'Domain name.', 'type': 'string'}},
 'required': ['domain'],
 'type': 'object'})
async def _domain_info(domain: str) -> dict:
    r = await _get('https://api.aa1.cn/api/api-icp/', {'domain': domain})
    return r

@tool('check_website', 'Run the check_website utility.', {'properties': {'url': {'description': 'URL.', 'type': 'string'}},
 'required': ['url'],
 'type': 'object'})
async def _check_website(url: str) -> dict:
    start = time.time()
    try:
        global _http
        if _http is None:
            _http = httpx.AsyncClient(timeout=10)
        resp = await _http.get(url, timeout=10, follow_redirects=True)
        elapsed = round((time.time() - start) * 1000)
        return {'status': resp.status_code, 'time_ms': elapsed, 'accessible': resp.status_code < 400}
    except Exception as e:
        return {'status': 0, 'time_ms': -1, 'accessible': False, 'error': str(e)}

@tool('generate_uuid', 'Run the generate_uuid utility.', {'properties': {'type': {'default': 'uuid4',
                         'description': 'type parameter.',
                         'enum': ['uuid4', 'ulid', 'nanoid'],
                         'type': 'string'}},
 'required': [],
 'type': 'object'})
async def _uuid(type: str='uuid4') -> dict:
    import uuid as _uuid_mod
    if type == 'uuid4':
        return {'id': str(_uuid_mod.uuid4()), 'type': 'uuid4'}
    elif type == 'ulid':
        import secrets as _s
        t = int(time.time() * 1000)
        return {'id': f'{t:012x}-{_s.token_hex(10)}', 'type': 'ulid'}
    else:
        import secrets as _s
        return {'id': _s.token_urlsafe(21), 'type': 'nanoid'}

@tool('hash_text', 'Run the hash_text utility.', {'properties': {'algorithm': {'default': 'md5',
                              'description': 'Algorithm name.',
                              'enum': ['md5', 'sha256', 'sha1'],
                              'type': 'string'},
                'text': {'description': 'Input text.', 'type': 'string'}},
 'required': ['text'],
 'type': 'object'})
async def _hash_text(text: str, algorithm: str='md5') -> dict:
    h = hashlib.new(algorithm, text.encode()).hexdigest()
    return {'hash': h, 'algorithm': algorithm, 'input_length': len(text)}

@tool('encode_decode', 'Run the encode_decode utility.', {'properties': {'action': {'description': 'action parameter.',
                           'enum': ['base64_encode', 'base64_decode', 'url_encode', 'url_decode'],
                           'type': 'string'},
                'text': {'description': 'Input text.', 'type': 'string'}},
 'required': ['text', 'action'],
 'type': 'object'})
async def _encode_decode(text: str, action: str) -> dict:
    import urllib.parse
    if action == 'base64_encode':
        return {'result': base64.b64encode(text.encode()).decode()}
    elif action == 'base64_decode':
        return {'result': base64.b64decode(text).decode()}
    elif action == 'url_encode':
        return {'result': urllib.parse.quote(text)}
    elif action == 'url_decode':
        return {'result': urllib.parse.unquote(text)}
    return {'error': 'unknown action'}

@tool('regex_test', 'Run the regex_test utility.', {'properties': {'pattern': {'description': 'Regex pattern.', 'type': 'string'},
                'text': {'description': 'Input text.', 'type': 'string'}},
 'required': ['pattern', 'text'],
 'type': 'object'})
async def _regex_test(pattern: str, text: str) -> dict:
    try:
        matches = re.findall(pattern, text)
        return {'matches': matches[:20], 'count': len(matches), 'pattern': pattern}
    except re.error as e:
        return {'error': str(e)}

@tool('json_format', 'Run the json_format utility.', {'properties': {'text': {'description': 'Input text.', 'type': 'string'}},
 'required': ['text'],
 'type': 'object'})
async def _json_format(text: str) -> dict:
    try:
        obj = json.loads(text)
        return {'valid': True, 'formatted': json.dumps(obj, indent=2, ensure_ascii=False)[:2000]}
    except json.JSONDecodeError as e:
        return {'valid': False, 'error': str(e)}
