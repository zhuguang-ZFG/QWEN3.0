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
                'model': 'claude-sonnet-4-6', 'fmt': 'anthropic', 'auth': 'x-api-key'},
    # LongCat 系列 - 按复杂度分层（使用 /anthropic/v1/messages 路径 + Bearer 认证）
    'longcat_lite':     {'url': 'https://api.longcat.chat/anthropic/v1/messages',
                         'key': os.environ.get('LONGCAT_API_KEY', ''),
                         'model': 'LongCat-Flash-Lite', 'fmt': 'anthropic', 'auth': 'bearer'},
    'longcat_chat':     {'url': 'https://api.longcat.chat/anthropic/v1/messages',
                         'key': os.environ.get('LONGCAT_API_KEY', ''),
                         'model': 'LongCat-Flash-Chat', 'fmt': 'anthropic', 'auth': 'bearer'},
    'longcat_thinking': {'url': 'https://api.longcat.chat/anthropic/v1/messages',
                         'key': os.environ.get('LONGCAT_API_KEY', ''),
                         'model': 'LongCat-Flash-Thinking-2601', 'fmt': 'anthropic', 'auth': 'bearer'},
    'longcat_omni':     {'url': 'https://api.longcat.chat/anthropic/v1/messages',
                         'key': os.environ.get('LONGCAT_API_KEY', ''),
                         'model': 'LongCat-Flash-Omni-2603', 'fmt': 'anthropic',
                         'auth': 'bearer', 'no_system': True},
    'longcat':          {'url': 'https://api.longcat.chat/anthropic/v1/messages',
                         'key': os.environ.get('LONGCAT_API_KEY', ''),
                         'model': 'LongCat-2.0-Preview', 'fmt': 'anthropic', 'auth': 'bearer'},
    # DeepSeek 系列
    'deepseek_pro':    {'url': 'https://api.deepseek.com/anthropic/v1/messages',
                        'key': os.environ.get('DEEPSEEK_API_KEY', ''),
                        'model': 'deepseek-v4-pro', 'fmt': 'anthropic'},
    'deepseek_pro_1m': {'url': 'https://api.deepseek.com/anthropic/v1/messages',
                        'key': os.environ.get('DEEPSEEK_API_KEY', ''),
                        'model': 'deepseek-v4-pro', 'fmt': 'anthropic'},
    'deepseek_flash':  {'url': 'https://api.deepseek.com/anthropic/v1/messages',
                        'key': os.environ.get('DEEPSEEK_API_KEY', ''),
                        'model': 'deepseek-v4-flash', 'fmt': 'anthropic'},
    'deepseek_flash_1m':{'url': 'https://api.deepseek.com/anthropic/v1/messages',
                         'key': os.environ.get('DEEPSEEK_API_KEY', ''),
                         'model': 'deepseek-v4-flash', 'fmt': 'anthropic'},
    'local':   {'url': LM_URL, 'key': '', 'model': 'local-model', 'fmt': 'openai', 'auth': 'bearer'},
}

# 对外暴露的统一模型名（用户永远看不到真实模型名）
PUBLIC_MODEL_NAME = os.environ.get('PUBLIC_MODEL_NAME', 'red V1flash')

# Intent -> backend
ROUTE = {
    'cnc_trouble':    'deepseek_pro',      # CNC故障 -> DeepSeek PRO（强推理）
    'grbl_config':    'local',             # GRBL参数 -> 本地（训练数据够用）
    'gcode_help':     'local',             # G代码 -> 本地
    'embedded_dev':   'deepseek_pro',      # 嵌入式开发 -> DeepSeek PRO
    'code_generation':'deepseek_flash',    # 代码生成 -> DeepSeek FLASH（快+强代码）
    'architecture':   'claude',            # 架构设计 -> Claude（最强综合）
    'general_cnc':    'longcat_lite',      # 通用CNC -> LongCat Lite（最快）
    'complex_theory': 'deepseek_pro',      # 复杂理论 -> DeepSeek PRO
    'unknown':        'longcat_chat',      # 未知 -> LongCat Chat
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
    (re.compile(r'deepseek[\w\-\.\[\]]*', re.IGNORECASE), PUBLIC_MODEL_NAME),
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

# ── Quality Assurance Layer ──────────────────────────────────────────────────
# GRBL 参数合理范围（防止 AI 编造错误参数值）
GRBL_PARAM_RANGES = {
    '$0': (1, 255),       '$1': (0, 255),       '$2': (0, 7),
    '$3': (0, 7),         '$4': (0, 1),          '$5': (0, 1),
    '$6': (0, 1),         '$10': (0, 255),       '$11': (0.0, 10.0),
    '$12': (0.0, 1.0),    '$13': (0, 1),         '$20': (0, 1),
    '$21': (0, 1),        '$22': (0, 1),         '$23': (0, 7),
    '$24': (1.0, 10000.0),'$25': (1.0, 100000.0),'$26': (0, 255),
    '$27': (0.0, 100.0),  '$30': (1, 100000),    '$31': (0, 100000),
    '$32': (0, 1),
    '$100': (1.0, 10000.0), '$101': (1.0, 10000.0), '$102': (1.0, 10000.0),
    '$110': (1.0, 100000.0),'$111': (1.0, 100000.0),'$112': (1.0, 100000.0),
    '$120': (1.0, 100000.0),'$121': (1.0, 100000.0),'$122': (1.0, 100000.0),
    '$130': (0.0, 100000.0),'$131': (0.0, 100000.0),'$132': (0.0, 100000.0),
}

# 不确定性信号词
UNCERTAINTY_SIGNALS = [
    '我不确定', '可能是', '大概', '也许', '不太清楚', '不确定',
    '需要更多信息', '取决于具体情况', '可能需要', '建议测试',
    'not sure', 'might be', 'possibly', 'uncertain',
]

# 免责声明模式（清洗掉）
DISCLAIMER_PATTERNS = [
    re.compile(r'作为AI.*?[。\n]', re.DOTALL),
    re.compile(r'我无法保证.*?[。\n]', re.DOTALL),
    re.compile(r'建议咨询专业.*?[。\n]', re.DOTALL),
    re.compile(r'请注意.*?安全.*?[。\n]', re.DOTALL),
    re.compile(r'以上仅供参考.*?[。\n]', re.DOTALL),
    re.compile(r'作为.*?语言模型.*?[。\n]', re.DOTALL),
]

def validate_grbl_params(text):
    """检测回答里的 GRBL 参数值是否在合理范围内，返回警告列表。"""
    warnings = []
    for match in re.finditer(r'(\$\d+)\s*[=:]\s*([\d.]+)', text):
        param = match.group(1)
        try:
            value = float(match.group(2))
        except ValueError:
            continue
        if param in GRBL_PARAM_RANGES:
            lo, hi = GRBL_PARAM_RANGES[param]
            if not (lo <= value <= hi):
                warnings.append(f'{param}={value} 超出合理范围 [{lo}, {hi}]')
    return warnings

def is_truncated(text):
    """检测回答是否被截断。"""
    if not text or len(text) < 20:
        return True
    if text.count('```') % 2 != 0:
        return True
    stripped = text.rstrip()
    if stripped and stripped[-1] not in '。！？.!?\n）)】]':
        if len(stripped) > 100 and stripped[-1].isalnum():
            return True
    return False

def detect_uncertainty(text):
    """检测回答是否包含不确定性信号。"""
    return any(s in text for s in UNCERTAINTY_SIGNALS)

def remove_disclaimers(text):
    """清洗掉常见的 AI 免责声明。"""
    for pattern in DISCLAIMER_PATTERNS:
        text = pattern.sub('', text)
    return text.strip()

def qa_check(text, intent=None, backend=None):
    """质量检查：验证参数范围、检测截断、清洗免责声明。
    返回 (checked_text, issues) 其中 issues 是问题列表。
    """
    issues = []
    text = remove_disclaimers(text)
    if is_truncated(text):
        issues.append('truncated')
    if intent and intent.get('cnc_subdomain') == 'grbl':
        param_warnings = validate_grbl_params(text)
        if param_warnings:
            issues.append('param_warning')
            text += '\n\n⚠️ 参数提示：' + '；'.join(param_warnings) + '，请结合实际硬件验证。'
    return text, issues

# ── API backend calls ────────────────────────────────────────────────────────
def call_api(name, msgs, mt=1024):
    """Call an external API backend."""
    b = BACKENDS.get(name)
    if not b or not b['key']:
        return f'[ERR] Backend {name} unavailable (no key)'
    auth_style = b.get('auth', 'x-api-key')
    if b['fmt'] == 'anthropic':
        # no_system 后端（如 Omni）：不传 system，content 用 list 格式
        if b.get('no_system'):
            omni_msgs = [
                {'role': m['role'],
                 'content': [{'type': 'text', 'text': m['content']}]
                             if isinstance(m['content'], str) else m['content']}
                for m in msgs
            ]
            body = {'model': b['model'], 'max_tokens': mt, 'messages': omni_msgs}
        else:
            body = {'model': b['model'], 'max_tokens': mt, 'system': SYS, 'messages': msgs}
        p = json.dumps(body).encode()
        if auth_style == 'bearer':
            h = {'Content-Type': 'application/json',
                 'Authorization': f"Bearer {b['key']}",
                 'anthropic-version': '2023-06-01'}
        else:
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
            answer = call_api('longcat_chat', [{'role': 'user', 'content': query}])
        result['answer'] = answer
    else:
        # Remote: expand prompt first
        expanded = expand(query, intent)
        result['expanded'] = expanded
        result['answer'] = call_api(backend, [{'role': 'user', 'content': expanded}])

    result['total_ms'] = int((time.time() - t0) * 1000)
    result['answer'] = clean_response(result.get('answer', ''), result.get('backend', ''))

    # 质量检查
    answer, issues = qa_check(result['answer'], intent=intent, backend=backend)
    result['answer'] = answer

    # 不确定性检测：自动升级到更强模型
    if detect_uncertainty(result['answer']) and backend not in ('claude', 'deepseek_pro'):
        upgraded = call_api('deepseek_pro', [{'role': 'user', 'content': query}])
        if not detect_uncertainty(upgraded):
            result['answer'] = clean_response(upgraded, 'deepseek_pro')
            result['upgraded'] = True

    # 截断检测：自动续写
    if 'truncated' in issues and backend != 'local':
        continuation = call_api(backend, [
            {'role': 'user', 'content': query},
            {'role': 'assistant', 'content': result['answer']},
            {'role': 'user', 'content': '请继续完成上面的回答。'},
        ], mt=512)
        if continuation and not continuation.startswith('[ERR]'):
            result['answer'] = result['answer'] + '\n' + clean_response(continuation, backend)

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
    parser.add_argument('--backend', '-b', type=str,
                        choices=['claude', 'longcat', 'longcat_lite', 'longcat_chat',
                                 'longcat_thinking', 'longcat_omni',
                                 'deepseek_pro', 'deepseek_pro_1m',
                                 'deepseek_flash', 'deepseek_flash_1m', 'local'])
    parser.add_argument('--json', action='store_true', help='Output JSON (for --query mode)')
    parser.add_argument('--test', action='store_true', help='测试所有后端连通性')
    args = parser.parse_args()

    if args.test:
        print('测试所有后端连通性...')
        test_msg = [{'role': 'user', 'content': '你好，回复"OK"即可'}]
        for name, b in BACKENDS.items():
            if name == 'local':
                resp = call_local([{'role': 'user', 'content': '你好'}], mt=10)
            else:
                resp = call_api(name, test_msg, mt=20)
            status = 'OK' if '暂时不可用' not in resp and 'ERR' not in resp else 'FAIL'
            print(f'  {name} ({b["model"]}): {status}')
        sys.exit(0)

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

