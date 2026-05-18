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
    # Nvidia NIM 系列 - 免费额度，OpenAI 兼容
    'nvidia_nemotron':  {'url': 'https://integrate.api.nvidia.com/v1/chat/completions',
                         'key': os.environ.get('NVIDIA_API_KEY', ''),
                         'model': 'nvidia/llama-3.3-nemotron-super-49b-v1', 'fmt': 'openai'},
    'nvidia_llama70b':  {'url': 'https://integrate.api.nvidia.com/v1/chat/completions',
                         'key': os.environ.get('NVIDIA_API_KEY', ''),
                         'model': 'meta/llama-3.3-70b-instruct', 'fmt': 'openai'},
    'nvidia_qwen_coder':{'url': 'https://integrate.api.nvidia.com/v1/chat/completions',
                         'key': os.environ.get('NVIDIA_API_KEY', ''),
                         'model': 'qwen/qwen3-coder-480b-a35b-instruct', 'fmt': 'openai'},
    'nvidia_llama4':    {'url': 'https://integrate.api.nvidia.com/v1/chat/completions',
                         'key': os.environ.get('NVIDIA_API_KEY', ''),
                         'model': 'meta/llama-4-maverick-17b-128e-instruct', 'fmt': 'openai'},
    'nvidia_mistral':   {'url': 'https://integrate.api.nvidia.com/v1/chat/completions',
                         'key': os.environ.get('NVIDIA_API_KEY', ''),
                         'model': 'mistralai/mistral-large-3-675b-instruct-2512', 'fmt': 'openai'},
    'nvidia_phi4':      {'url': 'https://integrate.api.nvidia.com/v1/chat/completions',
                         'key': os.environ.get('NVIDIA_API_KEY', ''),
                         'model': 'microsoft/phi-4-mini-instruct', 'fmt': 'openai'},
    # 中国移动 MaaS
    'chinamobile': {'url': 'https://maas.gd.chinamobile.com:36007/ai/uifm/open/v1/chat/completions',
                    'key': os.environ.get('CHINAMOBILE_API_KEY', ''),
                    'model': 'minimax-m25', 'fmt': 'openai'},
    # OpenRouter 免费模型（20次/分钟，200次/天，不稳定需熔断保护）
    'or_deepseek_r1':  {'url': 'https://openrouter.ai/api/v1/chat/completions',
                        'key': os.environ.get('OPENROUTER_API_KEY', ''),
                        'model': 'deepseek/deepseek-v4-flash:free', 'fmt': 'openai',
                        'timeout': 60},  # 免费模型响应慢，超时60秒
    'or_qwen3_235b':   {'url': 'https://openrouter.ai/api/v1/chat/completions',
                        'key': os.environ.get('OPENROUTER_API_KEY', ''),
                        'model': 'qwen/qwen3-coder:free', 'fmt': 'openai',
                        'timeout': 60},
    'or_llama70b':     {'url': 'https://openrouter.ai/api/v1/chat/completions',
                        'key': os.environ.get('OPENROUTER_API_KEY', ''),
                        'model': 'meta-llama/llama-3.3-70b-instruct:free', 'fmt': 'openai',
                        'timeout': 45},
    'or_nemotron':     {'url': 'https://openrouter.ai/api/v1/chat/completions',
                        'key': os.environ.get('OPENROUTER_API_KEY', ''),
                        'model': 'nvidia/nemotron-3-super-120b-a12b:free', 'fmt': 'openai',
                        'timeout': 60},
    'or_qwen3_30b':    {'url': 'https://openrouter.ai/api/v1/chat/completions',
                        'key': os.environ.get('OPENROUTER_API_KEY', ''),
                        'model': 'qwen/qwen3-next-80b-a3b-instruct:free', 'fmt': 'openai',
                        'timeout': 30},
    'local':   {'url': LM_URL, 'key': '', 'model': 'local-model', 'fmt': 'openai', 'auth': 'bearer'},
}

# 对外暴露的统一模型名（用户永远看不到真实模型名）
PUBLIC_MODEL_NAME = os.environ.get('PUBLIC_MODEL_NAME', 'red V1flash')

# Intent -> backend
# 路由策略：免费模型优先，按层级榨取，付费模型最后兜底
# L0=本地零成本 | L1=LongCat/中国移动免费无限 | L2=Nvidia免费额度 | L3=OpenRouter免费额度 | L4=付费兜底
ROUTE = {
    'cnc_trouble':    'longcat_thinking',  # L1: LongCat推理（免费，故障诊断）
    'grbl_config':    'local',             # L0: 本地直答，零成本
    'gcode_help':     'local',             # L0: 本地直答，零成本
    'embedded_dev':   'nvidia_nemotron',   # L2: Nvidia免费额度，嵌入式强
    'code_generation':'nvidia_qwen_coder', # L2: Nvidia免费额度，代码最强
    'architecture':   'longcat',           # L1: LongCat免费，综合最强
    'general_cnc':    'longcat_lite',      # L1: LongCat免费，快速
    'complex_theory': 'longcat_thinking',  # L1: LongCat免费推理
    'unknown':        'longcat_chat',      # L1: LongCat免费，通用
}

# ── Circuit Breaker ──────────────────────────────────────────────────────────
import threading

_cb_lock = threading.Lock()
_cb_state = {}  # backend_name -> state dict

CB_FAILURE_THRESHOLD = 3    # 连续失败 N 次后熔断
CB_RECOVERY_TIMEOUT  = 60   # 熔断后 N 秒尝试恢复（half-open）
CB_SUCCESS_THRESHOLD = 2    # half-open 状态下连续成功 N 次才关闭熔断

def _cb_get(name):
    with _cb_lock:
        if name not in _cb_state:
            _cb_state[name] = {
                'state': 'closed',   # closed / open / half-open
                'failures': 0,
                'successes': 0,
                'opened_at': 0,
                'total_calls': 0,
                'total_errors': 0,
                'total_latency_ms': 0,
            }
        return dict(_cb_state[name])

def cb_allow(name):
    """返回 True 表示允许调用，False 表示熔断中。"""
    s = _cb_get(name)
    if s['state'] == 'closed':
        return True
    if s['state'] == 'open':
        if time.time() - s['opened_at'] > CB_RECOVERY_TIMEOUT:
            with _cb_lock:
                _cb_state[name]['state'] = 'half-open'
                _cb_state[name]['successes'] = 0
            return True
        return False
    # half-open: 允许一次试探
    return True

def cb_record(name, success, latency_ms=0):
    """记录调用结果，更新熔断器状态。"""
    with _cb_lock:
        s = _cb_state.setdefault(name, {
            'state': 'closed', 'failures': 0, 'successes': 0,
            'opened_at': 0, 'total_calls': 0, 'total_errors': 0, 'total_latency_ms': 0,
        })
        s['total_calls'] += 1
        s['total_latency_ms'] += latency_ms
        if success:
            s['total_errors'] = max(0, s['total_errors'])
            if s['state'] == 'half-open':
                s['successes'] += 1
                if s['successes'] >= CB_SUCCESS_THRESHOLD:
                    s['state'] = 'closed'
                    s['failures'] = 0
                    if DEBUG:
                        print(f'[CB] {name}: half-open -> closed', file=sys.stderr)
            else:
                s['failures'] = 0
        else:
            s['total_errors'] += 1
            s['failures'] += 1
            if s['state'] in ('closed', 'half-open') and s['failures'] >= CB_FAILURE_THRESHOLD:
                s['state'] = 'open'
                s['opened_at'] = time.time()
                print(f'[CB] {name}: OPEN (circuit breaker tripped after {s["failures"]} failures)', file=sys.stderr)

def cb_status():
    """返回所有后端的熔断器状态摘要。"""
    result = {}
    with _cb_lock:
        for name, s in _cb_state.items():
            total = s['total_calls']
            err_rate = s['total_errors'] / total if total > 0 else 0
            avg_lat = s['total_latency_ms'] / total if total > 0 else 0
            result[name] = {
                'state': s['state'],
                'failures': s['failures'],
                'error_rate': f'{err_rate:.1%}',
                'avg_latency_ms': int(avg_lat),
                'total_calls': total,
            }
    return result

# ── Fallback Chains ──────────────────────────────────────────────────────────
# 降级顺序严格按层级：L1免费无限 -> L2Nvidia免费额度 -> L3OpenRouter免费额度 -> L4付费兜底
FALLBACK_CHAINS = {
    'cnc_trouble': [
        'longcat_thinking',   # L1: LongCat推理（免费）
        'longcat',            # L1: LongCat最强（免费）
        'chinamobile',        # L1: 中国移动（免费）
        'nvidia_nemotron',    # L2: Nvidia推理（免费额度）
        'or_nemotron',        # L3: OpenRouter Nemotron（免费额度）
        'or_deepseek_r1',     # L3: OpenRouter DeepSeek（免费额度）
        'deepseek_pro',       # L4: 付费兜底
        'claude',             # L4: 付费最终兜底
    ],
    'grbl_config': [
        'local',              # L0: 本地直答
        'longcat_lite',       # L1: LongCat（免费）
        'chinamobile',        # L1: 中国移动（免费）
        'nvidia_llama4',      # L2: Nvidia（免费额度）
        'or_llama70b',        # L3: OpenRouter（免费额度）
        'deepseek_flash',     # L4: 付费兜底
    ],
    'gcode_help': [
        'local',              # L0: 本地直答
        'longcat_lite',       # L1: LongCat（免费）
        'chinamobile',        # L1: 中国移动（免费）
        'nvidia_llama4',      # L2: Nvidia（免费额度）
        'or_llama70b',        # L3: OpenRouter（免费额度）
        'deepseek_flash',     # L4: 付费兜底
    ],
    'embedded_dev': [
        'nvidia_nemotron',    # L2: Nvidia嵌入式（免费额度）
        'longcat_thinking',   # L1: LongCat推理（免费）
        'longcat',            # L1: LongCat最强（免费）
        'or_nemotron',        # L3: OpenRouter Nemotron（免费额度）
        'or_deepseek_r1',     # L3: OpenRouter DeepSeek（免费额度）
        'deepseek_pro',       # L4: 付费兜底
        'claude',             # L4: 付费最终兜底
    ],
    'code_generation': [
        'nvidia_qwen_coder',  # L2: Qwen Coder 480B（免费额度，代码最强）
        'or_qwen3_235b',      # L3: OpenRouter Qwen3（免费额度）
        'longcat_chat',       # L1: LongCat（免费）
        'nvidia_llama70b',    # L2: Nvidia（免费额度）
        'or_llama70b',        # L3: OpenRouter（免费额度）
        'deepseek_flash',     # L4: 付费兜底
    ],
    'architecture': [
        'longcat',            # L1: LongCat最强（免费）
        'longcat_thinking',   # L1: LongCat推理（免费）
        'nvidia_nemotron',    # L2: Nvidia（免费额度）
        'or_deepseek_r1',     # L3: OpenRouter DeepSeek（免费额度）
        'deepseek_pro',       # L4: 付费兜底
        'claude',             # L4: 付费最终兜底
    ],
    'general_cnc': [
        'longcat_lite',       # L1: LongCat快速（免费）
        'chinamobile',        # L1: 中国移动（免费）
        'nvidia_llama4',      # L2: Nvidia快速（免费额度）
        'or_qwen3_30b',       # L3: OpenRouter快速（免费额度）
        'or_llama70b',        # L3: OpenRouter通用（免费额度）
        'deepseek_flash',     # L4: 付费兜底
    ],
    'complex_theory': [
        'longcat_thinking',   # L1: LongCat推理（免费）
        'longcat',            # L1: LongCat最强（免费）
        'nvidia_nemotron',    # L2: Nvidia推理（免费额度）
        'or_nemotron',        # L3: OpenRouter Nemotron（免费额度）
        'or_deepseek_r1',     # L3: OpenRouter DeepSeek（免费额度）
        'deepseek_pro',       # L4: 付费兜底
        'claude',             # L4: 付费最终兜底
    ],
    'unknown': [
        'longcat_chat',       # L1: LongCat通用（免费）
        'chinamobile',        # L1: 中国移动（免费）
        'nvidia_llama70b',    # L2: Nvidia通用（免费额度）
        'or_llama70b',        # L3: OpenRouter通用（免费额度）
        'or_qwen3_30b',       # L3: OpenRouter快速（免费额度）
        'longcat',            # L1: LongCat最强（免费，最终免费兜底）
        'deepseek_flash',     # L4: 付费兜底
    ],
}

def get_fallback_chain(intent_name, prefer=None):
    """获取意图对应的降级链，过滤掉没有 key 的后端。"""
    chain = list(FALLBACK_CHAINS.get(intent_name, ['nvidia_llama70b', 'longcat', 'claude']))
    # 如果有偏好后端，插到最前面
    if prefer and prefer in BACKENDS and prefer not in chain:
        chain.insert(0, prefer)
    elif prefer and prefer in chain:
        chain.remove(prefer)
        chain.insert(0, prefer)
    # 过滤掉没有 key 的后端
    chain = [b for b in chain if b in BACKENDS and (BACKENDS[b]['key'] or b == 'local')]
    return chain

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
    (re.compile(r'nvidia[\w\-\.\/]*', re.IGNORECASE), PUBLIC_MODEL_NAME),
    (re.compile(r'nemotron[\w\-\.]*', re.IGNORECASE), PUBLIC_MODEL_NAME),
    (re.compile(r'llama[\w\-\.]*', re.IGNORECASE), PUBLIC_MODEL_NAME),
    (re.compile(r'mistral[\w\-\.]*', re.IGNORECASE), PUBLIC_MODEL_NAME),
    (re.compile(r'qwen[\w\-\.]*', re.IGNORECASE), PUBLIC_MODEL_NAME),
    (re.compile(r'phi[\w\-\.]*', re.IGNORECASE), PUBLIC_MODEL_NAME),
    (re.compile(r'anthropic', re.IGNORECASE), ''),
    (re.compile(r'openai', re.IGNORECASE), ''),
    (re.compile(r'minimax[\w\-\.]*', re.IGNORECASE), PUBLIC_MODEL_NAME),
    (re.compile(r'MiniMax[\w\-\.]*', re.IGNORECASE), PUBLIC_MODEL_NAME),
    (re.compile(r'deepseek[\w\-\.\/\:]*r1[\w\-\.]*', re.IGNORECASE), PUBLIC_MODEL_NAME),
    (re.compile(r'qwen[\w\-\.\/\:]*235[\w\-\.]*', re.IGNORECASE), PUBLIC_MODEL_NAME),
    (re.compile(r'openrouter[\w\-\.\/]*', re.IGNORECASE), PUBLIC_MODEL_NAME),
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
    # 熔断检查
    if not cb_allow(name):
        if DEBUG:
            print(f'[CB] {name}: blocked by circuit breaker', file=sys.stderr)
        return None  # 返回 None 表示熔断，由调用方降级
    _t0 = time.time()
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
        _timeout = b.get('timeout', 60)
        with urllib.request.urlopen(r, timeout=_timeout) as resp:
            d = json.loads(resp.read().decode())
        if b['fmt'] == 'anthropic':
            answer = d['content'][0].get('text', json.dumps(d, ensure_ascii=False))
        else:
            msg = d['choices'][0]['message']
            # 推理模型（如 minimax-m25）content 可能为 None，回退到 reasoning 字段
            answer = msg.get('content') or msg.get('reasoning') or json.dumps(d, ensure_ascii=False)
        cb_record(name, True, int((time.time() - _t0) * 1000))
        return clean_response(answer, name)
    except Exception as e:
        print(f'[DEBUG] {name} error: {e}', file=sys.stderr)
        cb_record(name, False)
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

    # 获取降级链
    intent_name = intent.get('intent', 'unknown')
    fallback_chain = get_fallback_chain(intent_name, prefer=prefer)
    backend = fallback_chain[0] if fallback_chain else 'longcat'
    result['backend'] = backend
    result['fallback_chain'] = fallback_chain

    # 尝试降级链中的每个后端
    answer = None
    used_backend = backend
    expanded_q = query
    for attempt_backend in fallback_chain:
        if attempt_backend == 'local':
            ans = call_local([
                {'role': 'system', 'content': SYS},
                {'role': 'user', 'content': query},
            ], mt=800)
            if ans and not ans.startswith('[LOCAL_ERR]'):
                answer = ans
                used_backend = 'local'
                break
            continue

        expanded_q = expand(query, intent)
        ans = call_api(attempt_backend, [{'role': 'user', 'content': expanded_q}])
        if ans is not None and not ans.startswith('[ERR]') and '暂时不可用' not in ans:
            answer = ans
            used_backend = attempt_backend
            if attempt_backend != backend and DEBUG:
                print(f'[FALLBACK] {backend} -> {attempt_backend}', file=sys.stderr)
            break

    if answer is None:
        answer = '服务暂时不可用，请稍后重试'

    result['expanded'] = expanded_q
    result['backend'] = used_backend
    result['answer'] = answer

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

    # 写入蒸馏队列（失败不影响主流程）
    _log_to_distill_queue(query, result.get('answer', ''), intent, result.get('backend', ''))

    return result

# ── Distill Queue Logger ─────────────────────────────────────────────────────
DISTILL_QUEUE_DIR = os.path.join(os.path.dirname(__file__), 'data', 'distill_queue', 'pending')


def _quick_score(query: str, answer: str) -> float:
    """快速质量评分，纯本地规则，0ms延迟。返回 0.0-1.0。"""
    if not answer:
        return 0.0

    # 长度分（0.3权重）
    length = len(answer)
    if 100 <= length <= 2000:
        len_score = 1.0
    elif length < 50:
        len_score = 0.0
    elif length < 100:
        len_score = (length - 50) / 50
    else:  # > 2000
        len_score = max(0.7, 1.0 - (length - 2000) / 5000)

    # 格式分（0.3权重）
    fmt_score = 0.0
    if '```' in answer and answer.count('```') % 2 == 0:
        fmt_score += 0.4
    if any(c.isdigit() for c in answer):
        fmt_score += 0.3
    if any(marker in answer for marker in ['1.', '2.', '- ', '* ', '步骤']):
        fmt_score += 0.3

    # 完整性分（0.2权重）
    comp_score = 1.0
    bad_markers = ['抱歉', '无法', '不确定', '我不能', '暂时不可用']
    if any(m in answer for m in bad_markers):
        comp_score = 0.3

    # 相关性分（0.2权重）
    query_words = set(query.lower().replace('?', '').replace('？', '').split())
    answer_lower = answer.lower()
    if query_words:
        overlap = sum(1 for w in query_words if w in answer_lower and len(w) > 1)
        rel_score = min(1.0, overlap / max(len(query_words) * 0.3, 1))
    else:
        rel_score = 0.5

    total = len_score * 0.3 + fmt_score * 0.3 + comp_score * 0.2 + rel_score * 0.2
    return round(total, 3)

def _log_to_distill_queue(query: str, answer: str, intent: dict, backend: str) -> None:
    """将路由结果写入蒸馏队列，供 distill_scheduler 使用。

    只记录满足以下条件的条目：
    1. 后端不是 'local'（本地模型回答不需要蒸馏）
    2. 回答不含错误标志
    3. 日志功能已启用（DISTILL_LOG=1 环境变量）
    """
    if os.environ.get('DISTILL_LOG', '0') != '1':
        return
    if backend == 'local':
        return
    if not answer or '暂时不可用' in answer:
        return

    try:
        os.makedirs(DISTILL_QUEUE_DIR, exist_ok=True)
        import hashlib, datetime
        score = _quick_score(query, answer)
        entry = {
            'query': query,
            'answer': answer,
            'intent': intent.get('intent', 'unknown'),
            'complexity': intent.get('complexity', 0.5),
            'source_backend': backend,
            'quality_score': score,
            'routing_correct': score >= 0.7,
            'logged_at': datetime.datetime.now().isoformat(),
        }
        qhash = hashlib.md5(query.encode()).hexdigest()[:8]
        ts = time.strftime('%Y%m%d_%H%M%S')
        fname = os.path.join(DISTILL_QUEUE_DIR, f'{ts}_{qhash}.json')
        with open(fname, 'w', encoding='utf-8') as f:
            json.dump(entry, f, ensure_ascii=False, indent=2)
        if DEBUG:
            print(f'[DISTILL] logged: {query[:30]}... -> {backend}', file=sys.stderr)
    except Exception as e:
        if DEBUG:
            print(f'[DISTILL] log failed: {e}', file=sys.stderr)

# ── Pressure Test ────────────────────────────────────────────────────────────
def pressure_test(backends=None, concurrency=3, rounds=5):
    """对指定后端进行压力测试，报告成功率、延迟、稳定性。"""
    import concurrent.futures

    test_queries = [
        'GRBL $100 参数怎么设置',
        '步进电机失步怎么排查',
        '写一个 ESP32 读取编码器的代码',
        'G2 圆弧插补的 IJK 参数怎么用',
        'FreeRTOS 任务优先级怎么设置',
    ]

    if backends is None:
        backends = [b for b, cfg in BACKENDS.items() if cfg.get('key') or b == 'local']

    print(f'\n压力测试: {len(backends)} 个后端, 并发={concurrency}, 轮次={rounds}')
    print('=' * 70)

    results = {}

    for backend in backends:
        if backend == 'local' and not BACKENDS['local']['key']:
            resp = call_local([{'role': 'user', 'content': 'hi'}], mt=5)
            if resp.startswith('[LOCAL_ERR]'):
                print(f'  {backend:20s}: SKIP (LM Studio 未运行)')
                continue

        successes = 0
        failures = 0
        latencies = []
        errors = []

        def single_test(q, _b=backend):
            t0 = time.time()
            if _b == 'local':
                resp = call_local([{'role': 'user', 'content': q}], mt=50)
                ok = resp and not resp.startswith('[LOCAL_ERR]')
            else:
                resp = call_api(_b, [{'role': 'user', 'content': q}], mt=50)
                ok = resp is not None and '暂时不可用' not in str(resp) and not str(resp).startswith('[ERR]')
            lat = int((time.time() - t0) * 1000)
            return ok, lat, resp

        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as ex:
            futures = [ex.submit(single_test, test_queries[i % len(test_queries)]) for i in range(rounds)]
            for f in concurrent.futures.as_completed(futures):
                ok, lat, resp = f.result()
                if ok:
                    successes += 1
                    latencies.append(lat)
                else:
                    failures += 1
                    if resp:
                        errors.append(str(resp)[:50])

        total = successes + failures
        rate = successes / total * 100 if total > 0 else 0
        avg_lat = sum(latencies) / len(latencies) if latencies else 0
        p95_lat = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0

        status = 'STABLE' if rate >= 80 else ('UNSTABLE' if rate >= 50 else 'UNRELIABLE')
        model = BACKENDS.get(backend, {}).get('model', 'local')[:35]

        print(f'  {backend:20s} [{status:10s}] 成功率={rate:.0f}% avg={avg_lat:.0f}ms p95={p95_lat:.0f}ms  ({model})')
        if errors:
            print(f'    错误样本: {errors[0]}')

        results[backend] = {
            'status': status, 'success_rate': rate,
            'avg_latency_ms': avg_lat, 'p95_latency_ms': p95_lat,
        }

        # 重置熔断器（测试后恢复）
        with _cb_lock:
            if backend in _cb_state:
                _cb_state[backend]['state'] = 'closed'
                _cb_state[backend]['failures'] = 0

    print('=' * 70)
    print(f'测试完成。稳定后端: {[b for b, r in results.items() if r["status"] == "STABLE"]}')
    return results

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
                                 'deepseek_flash', 'deepseek_flash_1m',
                                 'nvidia_nemotron', 'nvidia_llama70b',
                                 'nvidia_qwen_coder', 'nvidia_llama4',
                                 'nvidia_mistral', 'nvidia_phi4', 'local'])
    parser.add_argument('--json', action='store_true', help='Output JSON (for --query mode)')
    parser.add_argument('--test', action='store_true', help='测试所有后端连通性')
    parser.add_argument('--pressure-test', action='store_true', help='对所有后端进行压力测试')
    parser.add_argument('--status', action='store_true', help='显示熔断器状态')
    parser.add_argument('--backends', type=str, help='指定测试的后端（逗号分隔）')
    args = parser.parse_args()

    if args.pressure_test:
        blist = args.backends.split(',') if args.backends else None
        pressure_test(backends=blist)
        sys.exit(0)
    if args.status:
        status = cb_status()
        if not status:
            print('暂无调用记录')
        else:
            for name, s in status.items():
                print(f'  {name:20s}: {s["state"]:10s} 错误率={s["error_rate"]} 平均延迟={s["avg_latency_ms"]}ms 总调用={s["total_calls"]}')
        sys.exit(0)

    if args.test:
        print('测试所有后端连通性...')
        test_msg = [{'role': 'user', 'content': '你好，回复"OK"即可'}]
        for name, b in BACKENDS.items():
            if name == 'local':
                resp = call_local([{'role': 'user', 'content': '你好'}], mt=10)
            else:
                resp = call_api(name, test_msg, mt=20)
            status = 'OK' if resp and '暂时不可用' not in str(resp) and 'ERR' not in str(resp) else 'FAIL'
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

