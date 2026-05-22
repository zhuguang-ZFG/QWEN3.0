#!/usr/bin/env python3
"""LiMa 零 Key 端点集成测试
验证 ch.at / DevToolBox / Pollinations / LLM7.io 可用性
运行: python tests/test_zerokey_endpoints.py

NOTE: 这是手工 smoke 测试，不应被 pytest 自动收集。
"""
import pytest
pytestmark = pytest.mark.skip(reason="Manual smoke test — requires external network access")

import urllib.request, json, time, sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PASS = 0
FAIL = 0
RESULTS = []

def test(name, func):
    global PASS, FAIL
    t0 = time.time()
    try:
        result = func()
        ms = int((time.time() - t0) * 1000)
        PASS += 1
        RESULTS.append(('✓', name, f'{ms}ms', result[:60]))
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        FAIL += 1
        RESULTS.append(('✗', name, f'{ms}ms', str(e)[:60]))

def http_post(url, payload, timeout=20):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={
        'Content-Type': 'application/json', 'User-Agent': 'LiMa/2.0'})
    resp = urllib.request.urlopen(req, timeout=timeout)
    return resp.read().decode('utf-8', errors='replace')

def http_get(url, timeout=15):
    req = urllib.request.Request(url, headers={'User-Agent': 'LiMa/2.0'})
    resp = urllib.request.urlopen(req, timeout=timeout)
    return resp.read().decode('utf-8', errors='replace')

# ═══════════════════════════════════════════════════════════════
# ch.at (Universal Basic Intelligence, OpenAI-compat, 零限制)
# ═══════════════════════════════════════════════════════════════

def test_chat_ubi():
    r = http_post('https://ch.at/v1/chat/completions', {
        'messages': [{'role': 'user', 'content': '2+2=? One number only.'}]
    })
    data = json.loads(r)
    content = data['choices'][0]['message']['content']
    return content.strip()[:60]

# ═══════════════════════════════════════════════════════════════
# DevToolBox Workers API (Cloudflare Workers)
# ═══════════════════════════════════════════════════════════════

DTB = 'https://devtoolbox-api.devtoolbox-api.workers.dev/ai'

def test_dtb_sql():
    r = http_post(f'{DTB}/sql', {'description': 'find users registered in last 30 days'})
    data = json.loads(r)
    return (data.get('sql', '') or str(data))[:60]

def test_dtb_regex():
    r = http_post(f'{DTB}/regex', {'description': 'match email addresses'})
    data = json.loads(r)
    return (data.get('regex', '') or str(data))[:60]

def test_dtb_fix_code():
    r = http_post(f'{DTB}/fix-code', {'code': 'def add(a, b:\n  return a + b'})
    data = json.loads(r)
    return (data.get('fix', '') or str(data))[:60]

# ═══════════════════════════════════════════════════════════════
# Pollinations AI
# ═══════════════════════════════════════════════════════════════

def test_pollinations_get():
    r = http_get('https://text.pollinations.ai/What%20is%202+2%3F%20One%20word.', timeout=20)
    return r.strip()[:60]

def test_pollinations_image():
    req = urllib.request.Request(
        'https://image.pollinations.ai/prompt/red%20circle?width=256&height=256&nologo=true',
        headers={'User-Agent': 'LiMa/2.0'})
    resp = urllib.request.urlopen(req, timeout=30)
    size = len(resp.read())
    assert size > 1000, f'Too small: {size}B'
    return f'Image OK ({size} bytes)'

# ═══════════════════════════════════════════════════════════════
# LLM7.io
# ═══════════════════════════════════════════════════════════════

def test_llm7():
    r = http_post('https://api.llm7.io/v1/chat/completions', {
        'model': 'auto', 'messages': [{'role':'user','content':'3*7=?'}], 'max_tokens': 10
    })
    data = json.loads(r)
    model = data.get('model', '?')
    content = data['choices'][0]['message']['content']
    return f'[{model}] {content[:40]}'

# ═══════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print('LiMa Zero-Key Endpoint Tests (4 providers, 8 tests)')
    print('=' * 55)

    print('\n[1] ch.at — Universal Basic Intelligence')
    test('ch.at Chat', test_chat_ubi)

    print('\n[2] DevToolBox Workers — Tool APIs')
    test('DevToolBox /ai/sql', test_dtb_sql)
    test('DevToolBox /ai/regex', test_dtb_regex)
    test('DevToolBox /ai/fix-code', test_dtb_fix_code)

    print('\n[3] Pollinations — Chat + Image')
    test('Pollinations GET', test_pollinations_get)
    test('Pollinations Image', test_pollinations_image)

    print('\n[4] LLM7.io — Auto Router')
    test('LLM7.io Chat', test_llm7)

    print('\n' + '-' * 55)
    for s, name, lat, detail in RESULTS:
        print(f'  {s} {name:<25} {lat:>6}  {detail}')
    print(f'\n  {PASS}/{PASS+FAIL} passed')
    sys.exit(0 if FAIL == 0 else 1)
