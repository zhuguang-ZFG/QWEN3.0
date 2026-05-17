#!/usr/bin/env python3
"""red V1-Flash Smart Router
Two-layer routing: fast rules (80%) + local model (20% ambiguous)
Local model: intent analysis + prompt expansion
External APIs: Claude (complex), LongCat (code/general), local (simple CNC)
"""
import json, os, sys, re, time, urllib.request
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from dotenv import load_dotenv
load_dotenv()

DEBUG = os.environ.get('RED_DEBUG', '') == '1'

# ── Config ──────────────────────────────────────────────────────────────────
LM_URL = 'http://localhost:1234/v1/chat/completions'

BACKENDS = {
    'claude':  {'url': 'https://right.codes/claude-aws/v1/messages',
                'key': os.environ.get('CLAUDE_API_KEY', ''),
                'model': 'claude-sonnet-4-6', 'fmt': 'anthropic'},
    'longcat': {'url': 'https://api.longcat.chat/anthropic',
                'key': os.environ.get('LONGCAT_API_KEY', ''),
                'model': 'LongCat-2.0-Preview', 'fmt': 'anthropic'},
    'local':   {'url': LM_URL, 'key': '', 'model': 'local-model', 'fmt': 'openai'},
}

# 对外暴露的统一模型名（用户永远看不到真实模型名）
PUBLIC_MODEL_NAME = os.environ.get('PUBLIC_MODEL_NAME', 'red V1flash')

# Intent -> backend
ROUTE = {
    'cnc_trouble':    'claude',
    'grbl_config':    'local',
    'gcode_help':     'local',
    'embedded_dev':   'claude',
    'code_generation':'longcat',
    'architecture':   'claude',
    'general_cnc':    'local',
    'complex_theory': 'claude',
    'unknown':        'longcat',
}

SYS = 'CNC/embedded expert. Detailed Chinese answers with params, code, steps. No disclaimers.'

# ── Layer 1: Fast keyword rules ──────────────────────────────────────────────
RULES = [
    # (pattern, intent, confidence)
    (r'\$\d+|步数.*mm|steps.*mm|steps_per_mm', 'grbl_config', 0.95),
    (r'归零|homing|\$22|\$23|\$24|\$25|\$26|\$27', 'grbl_config', 0.95),
    (r'G0|G1|G2|G3|G28|G38|G54|G92|M3|M5|M8|圆弧|插补|进给', 'gcode_help', 0.90),
    (r'error:\d+|alarm:\d+|ALARM|报警|错误码', 'grbl_config', 0.90),
    (r'失步|抖动|噪音|异响|卡顿|不动|乱走|偏移', 'cnc_trouble', 0.85),
    (r'限位|limit switch|触发|短路|接线', 'cnc_trouble', 0.85),
    (r'ESP32|WiFi|蓝牙|WebUI|OTA|FreeRTOS|RTOS', 'embedded_dev', 0.85),
    (r'STM32|HAL|CubeMX|定时器|中断|DMA|寄存器', 'embedded_dev', 0.85),
    (r'写.*代码|生成.*代码|实现.*函数|代码示例', 'code_generation', 0.85),
    (r'架构|设计|方案|选型|对比|哪个好', 'architecture', 0.80),
    (r'FOC|PID|闭环|编码器|伺服|变频器|VFD', 'complex_theory', 0.85),
    (r'PCB|雕刻|激光|切割|主轴|转速|RPM', 'general_cnc', 0.80),
]

def rule_classify(query):
    """Layer 1: fast keyword matching. Returns (intent, confidence) or None."""
    best_intent, best_conf = None, 0.0
    for pattern, intent, conf in RULES:
        if re.search(pattern, query, re.IGNORECASE):
            if conf > best_conf:
                best_intent, best_conf = intent, conf
    if best_conf >= 0.80:
        return {'intent': best_intent, 'complexity': 0.5,
                'needs_code': 'code' in best_intent,
                'domain_keywords': [], 'cnc_subdomain': 'general',
                'source': 'rules', 'confidence': best_conf}
    return None

# ── Layer 2: Local model ─────────────────────────────────────────────────────
def call_local(msgs, mt=512, t=0.3):
    """Call LM Studio (OpenAI-compatible)."""
    p = json.dumps({'model': 'local-model', 'messages': msgs,
                    'max_tokens': mt, 'temperature': t}).encode()
    try:
        r = urllib.request.Request(LM_URL, data=p,
                                   headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(r, timeout=30) as resp:
            d = json.loads(resp.read().decode())
        return d['choices'][0]['message']['content']
    except Exception as e:
        return f'[LOCAL_ERR] {e}'

def model_classify(query):
    """Layer 2: local model intent classification for ambiguous queries."""
    prompt = (
        "Analyze this CNC/embedded user query. Output ONLY a JSON object.\n\n"
        f"Query: {query[:500]}\n\n"
        "JSON fields:\n"
        "- intent: cnc_trouble|grbl_config|gcode_help|embedded_dev|code_generation|architecture|general_cnc|complex_theory|unknown\n"
        "- complexity: 0.0 to 1.0\n"
        "- needs_code: true or false\n"
        "- domain_keywords: list of 1-3 key terms\n"
        "- cnc_subdomain: grbl|esp32|stm32|arduino|pcb|mechanical|spindle|stepper|gcode|general\n\n"
        'Example: {"intent":"cnc_trouble","complexity":0.7,"needs_code":false,'
        '"domain_keywords":["stepper","lost steps"],"cnc_subdomain":"stepper"}\n\nJSON:'
    )
    resp = call_local([
        {'role': 'system', 'content': 'Intent classifier. Output ONLY valid JSON.'},
        {'role': 'user', 'content': prompt},
    ], mt=200, t=0.1)
    try:
        txt = resp.strip()
        if txt.startswith('```'):
            txt = txt.split('```')[1]
            if txt.startswith('json'):
                txt = txt[4:]
        result = json.loads(txt.strip())
        result['source'] = 'model'
        return result
    except Exception:
        return {'intent': 'unknown', 'complexity': 0.5, 'needs_code': False,
                'domain_keywords': [], 'cnc_subdomain': 'general', 'source': 'fallback'}

def analyze(query):
    """Two-layer intent analysis: rules first, model if ambiguous."""
    result = rule_classify(query)
    if result:
        return result
    return model_classify(query)

# ── Prompt expansion ─────────────────────────────────────────────────────────
def expand(query, intent):
    """Expand short query into detailed technical prompt using local model."""
    prompt = (
        "As a CNC/embedded expert, rewrite this short user query into a detailed "
        "technical question for an AI expert. Add specific technical context. "
        "Under 300 chars. Chinese. Output ONLY the expanded question.\n\n"
        f"Query: {query}\n"
        f"Intent: {intent.get('intent', 'unknown')}\n"
        f"Domain: {intent.get('cnc_subdomain', 'general')}\n\n"
        "Expanded:"
    )
    resp = call_local([{'role': 'user', 'content': prompt}], mt=200, t=0.3)
    stripped = resp.strip()
    if not stripped or stripped.startswith('[LOCAL_ERR]') or stripped.startswith('{'):
        return query
    return stripped

# ── Response cleaning ────────────────────────────────────────────────────────
CLEAN_PATTERNS = [
    (re.compile(r'claude[\w\-\.]*', re.IGNORECASE), PUBLIC_MODEL_NAME),
    (re.compile(r'longcat[\w\-\.]*', re.IGNORECASE), PUBLIC_MODEL_NAME),
    (re.compile(r'gpt-?4[\w\-\.]*', re.IGNORECASE), PUBLIC_MODEL_NAME),
    (re.compile(r'anthropic', re.IGNORECASE), ''),
    (re.compile(r'openai', re.IGNORECASE), ''),
]

def clean_response(text, backend_name=''):
    """清洗响应：隐藏底层模型/供应商信息。"""
    if not text or '[ERR]' in text[:15]:
        return '服务暂时不可用，请稍后重试'
    for pattern, repl in CLEAN_PATTERNS:
        text = pattern.sub(repl, text)
    return text

# ── API backend calls ────────────────────────────────────────────────────────
def call_api(name, msgs, mt=1024):
    """Call an external API backend."""
    b = BACKENDS.get(name)
    if not b or not b['key']:
        return f'[ERR] Backend {name} unavailable (no key)'
    if b['fmt'] == 'anthropic':
        p = json.dumps({'model': b['model'], 'max_tokens': mt,
                        'system': SYS, 'messages': msgs}).encode()
        h = {'Content-Type': 'application/json',
             'x-api-key': b['key'], 'anthropic-version': '2023-06-01'}
    else:
        p = json.dumps({'model': b['model'], 'max_tokens': mt,
                        'messages': [{'role': 'system', 'content': SYS}] + msgs}).encode()
        h = {'Content-Type': 'application/json',
             'Authorization': f"Bearer {b['key']}"}
    try:
        r = urllib.request.Request(b['url'], data=p, headers=h)
        with urllib.request.urlopen(r, timeout=60) as resp:
            d = json.loads(resp.read().decode())
        if b['fmt'] == 'anthropic':
            answer = d['content'][0].get('text', json.dumps(d, ensure_ascii=False))
        else:
            answer = d['choices'][0]['message']['content']
        return clean_response(answer, name)
    except Exception as e:
        print(f'[DEBUG] {name} error: {e}', file=sys.stderr)
        return '服务暂时不可用，请稍后重试'

# ── Main router ──────────────────────────────────────────────────────────────
def route(query, prefer=None):
    """Route a query: analyze intent -> expand -> call best backend."""
    t0 = time.time()
    result = {'query': query}

    # Intent analysis (two-layer)
    intent = analyze(query)
    result['intent'] = intent
    result['classify_ms'] = int((time.time() - t0) * 1000)

    # Backend selection
    backend = prefer if prefer in BACKENDS else ROUTE.get(intent.get('intent', 'unknown'), 'longcat')
    result['backend'] = backend

    # Local: answer directly, skip expansion
    if backend == 'local':
        result['expanded'] = query
        answer = call_local([
            {'role': 'system', 'content': SYS},
            {'role': 'user', 'content': query},
        ], mt=800)
        if answer.startswith('[LOCAL_ERR]'):
            answer = call_api('longcat', [{'role': 'user', 'content': query}])
        result['answer'] = answer
    else:
        # Remote: expand prompt first
        expanded = expand(query, intent)
        result['expanded'] = expanded
        result['answer'] = call_api(backend, [{'role': 'user', 'content': expanded}])

    result['total_ms'] = int((time.time() - t0) * 1000)
    result['answer'] = clean_response(result.get('answer', ''), result.get('backend', ''))
    return result

# ── CLI mode ─────────────────────────────────────────────────────────────────
def cli():
    print('red V1-Flash Smart Router  (q to quit)')
    print('Powered by red V1flash')
    print('-' * 60)
    while True:
        try:
            q = input('\nYou: ').strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not q:
            continue
        if q.lower() in ('q', 'quit', 'exit'):
            break
        print('[Routing...]', end=' ', flush=True)
        r = route(q)
        src = r['intent'].get('source', '?')
        print(f"[{src}] intent={r['intent']['intent']} "
              f"complexity={r['intent']['complexity']} "
              f"-> red V1flash ({r['classify_ms']}ms classify, {r['total_ms']}ms total)")
        if DEBUG and r.get('expanded') != q:
            print(f'[Expanded]: {r["expanded"][:120]}')
        print(f'[Answer]:\n{r["answer"]}')
        print('-' * 60)

# ── MCP server mode ──────────────────────────────────────────────────────────
def mcp():
    """MCP stdio server for Claude Code integration."""
    print('MCP Server ready (stdio)', file=sys.stderr)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
            # 通知消息没有 id，静默忽略
            if 'id' not in msg:
                continue
            rid = msg.get('id')
            method = msg.get('method', '')
            params = msg.get('params', {})

            if method == 'initialize':
                resp = {'id': rid, 'result': {
                    'protocolVersion': '2024-11-05',
                    'capabilities': {'tools': {}},
                    'serverInfo': {'name': 'red-v1-flash', 'version': '1.0.0'},
                }}
            elif method == 'tools/list':
                resp = {'id': rid, 'result': {'tools': [
                    {
                        'name': 'cnc_route',
                        'description': 'Analyze CNC/embedded query, expand with technical context, route to best AI backend (Claude/LongCat/local)',
                        'inputSchema': {
                            'type': 'object',
                            'properties': {
                                'query': {'type': 'string', 'description': 'User CNC/embedded question'},
                                'prefer_backend': {'type': 'string', 'enum': ['claude', 'longcat', 'local']},
                            },
                            'required': ['query'],
                        },
                    },
                    {
                        'name': 'grbl_lookup',
                        'description': 'Look up GRBL parameter ($0-$132), error code (error:N), alarm (alarm:N), or G-code command',
                        'inputSchema': {
                            'type': 'object',
                            'properties': {
                                'item': {'type': 'string', 'description': 'e.g. $100, error:1, G2, M3'},
                            },
                            'required': ['item'],
                        },
                    },
                ]}}
            elif method == 'tools/call':
                name = params.get('name', '')
                args = params.get('arguments', {})
                if name == 'cnc_route':
                    r = route(args.get('query', ''), prefer=args.get('prefer_backend'))
                    text = json.dumps({
                        'intent': r['intent']['intent'],
                        'complexity': r['intent']['complexity'],
                        'answer': r['answer'],
                        'timing_ms': r['total_ms'],
                    }, ensure_ascii=False, indent=2)
                    resp = {'id': rid, 'result': {'content': [{'type': 'text', 'text': text}]}}
                elif name == 'grbl_lookup':
                    item = args.get('item', '')
                    if not re.match(r'^[\$\w\d\:\.\-]{1,30}$', item):
                        resp = {'id': rid, 'error': {'code': -32602, 'message': 'Invalid item format'}}
                        sys.stdout.write(json.dumps(resp) + '\n')
                        sys.stdout.flush()
                        continue
                    answer = call_local([
                        {'role': 'system', 'content': 'GRBL expert. Direct detailed Chinese answers.'},
                        {'role': 'user', 'content': f'Explain GRBL {item}: meaning, typical values, usage examples, common mistakes.'},
                    ], mt=500)
                    resp = {'id': rid, 'result': {'content': [{'type': 'text', 'text': answer}]}}
                else:
                    resp = {'id': rid, 'error': {'code': -32601, 'message': f'Unknown tool: {name}'}}
            else:
                resp = {'id': rid, 'result': {}}

            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + '\n')
            sys.stdout.flush()
        except Exception as e:
            err = {'id': None, 'error': {'code': -32700, 'message': str(e)}}
            sys.stdout.write(json.dumps(err) + '\n')
            sys.stdout.flush()

# ── Entry point ──────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='red V1-Flash Smart Router')
    parser.add_argument('--mcp', action='store_true', help='Run as MCP server for Claude Code')
    parser.add_argument('--query', '-q', type=str, help='Single query mode')
    parser.add_argument('--backend', '-b', type=str, choices=['claude', 'longcat', 'local'])
    parser.add_argument('--json', action='store_true', help='Output JSON (for --query mode)')
    args = parser.parse_args()

    if args.mcp:
        mcp()
    elif args.query:
        r = route(args.query, prefer=args.backend)
        if args.json:
            print(json.dumps(r, ensure_ascii=False, indent=2))
        else:
            print(f"Intent: {r['intent']['intent']} ({r['intent'].get('source','?')}) -> {r['backend']}")
            print(f"Answer: {r['answer']}")
    else:
        cli()

