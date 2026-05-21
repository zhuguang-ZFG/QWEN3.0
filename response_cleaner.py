"""
LiMa Response Cleaner — 响应清洗模块

从 http_caller.py 提取，负责：
- 品牌名替换（隐藏底层模型/供应商信息）
- 身份声明模式替换
- 后端错误消息检测
"""

import re

from backends import PUBLIC_MODEL_NAME

# ── Brand Patterns ────────────────────────────────────────────────────────────

# Brand names to replace with LiMa (sorted by priority: specific → general)
_BRANDS = [
    # Anthropic ecosystem
    'claude', 'longcat',
    # Chinese LLM companies & models
    'deepseek', '深度求索',
    'glm', 'chatglm', '智谱',
    'qwen', '通义千问',
    'ernie', '文心一言', '文心',
    'hunyuan', '混元',
    'doubao', '豆包',
    'kimi', '月之暗面',
    'minimax', '海螺',
    'metaso', '秘塔',
    'step', '阶跃星辰',
    'spark', '讯飞', '星火',
    'baichuan', '百川',
    'yi', 'yi-series', 'yi-model', '零一万物',
    # Western providers
    'openai', 'chatgpt',
    'anthropic',
    'google', 'gemini', 'gemma',
    'mistral', 'codestral', 'pixtral', 'devstral',
    'nvidia', 'nemotron',
    'llama',
    'meta-ai', 'meta ai',
    'phi-3', 'phi-4',
    'cohere', 'command-a', 'command-r',
    'cerebras',
    'groq',
    'cloudflare',
    'sambanova',
    'deepinfra',
    'fireworks',
    'together[\s-]?ai',
    'ai21',
    'jamba',
    # Zero-key / community providers
    'pollinations',
    'ovhcloud',
    'hermes',
    'naga[\s-]?ai',
    'freetheai',
    'zukijourney',
    'featherless',
    'glhf',
    'agentrouter',
    'llm7',
    'chatubi',
    'uncloseai',
    'opencode',
    # Chinese cloud providers
    'siliconflow', '硅基流动',
    'volcengine', '火山引擎',
    'alibaba', 'aliyun', 'dashscope', '阿里云',
    'baidu', '百度',
    'tencent', '腾讯',
    'chinamobile', '中国移动',
    'iflytek',
    # Generic model descriptors
    'gpt-3', 'gpt-4', 'gpt-5', 'gpt-oss',
    'openrouter',
]

# Build brand-name cleaning regexes.
# ASCII brands: \bBrandName[\w\-.]*  (word boundary + word-char suffix)
# CJK brands: literal match only, NO greedy suffix (would eat following verbs)
def _build_brand_re(brand: str) -> re.Pattern:
    escaped = re.escape(brand)
    if brand[0].isascii():
        return re.compile(rf'\b{escaped}[\w\-\.\[\]\/\:]*', re.I)
    # CJK: match brand name literally, don't extend into surrounding text
    return re.compile(rf'{escaped}', re.I)

BRAND_PATTERNS = [(_build_brand_re(b), PUBLIC_MODEL_NAME) for b in _BRANDS]

# ── Identity Patterns ─────────────────────────────────────────────────────────

# Specific identity-statement patterns (must run AFTER brand patterns)
IDENTITY_PATTERNS = [
    # English: "I am [X], made by [Y]" — but don't match "I am LiMa"
    (re.compile(r"\bI (?:am|'m) (?:an? )?(?:AI (?:language )?model|large language model)(?!.*LiMa)", re.I),
     f'I am an AI language model'),
    # English: "developed/created/trained by [Company]" — only if company not already cleaned
    (re.compile(r'(?:developed|created|trained|made|built|powered) by\s+[\w\s\-\.]+', re.I),
     f'developed by DongLiCao'),
    # Chinese: "我是 [X]的[AI/语言]模型" — requires model keyword
    (re.compile(r'我是(?:由|一个|一款)[\w\s\-\.一-鿿()（）]+?(?:开发|训练|创建|制作|创造|推出|提供)的(?:\s*(?:AI|人工智能|大语言|语言|对话))?\s*模型', re.I),
     f'我是{PUBLIC_MODEL_NAME}'),
    # Chinese: "我是一个 [AI/语言/大] 模型"
    (re.compile(r'我是(?:一个|一款)\s*(?:AI|人工智能|大语言|语言|对话)\s*模型', re.I),
     f'我是{PUBLIC_MODEL_NAME}'),
    # Chinese: "我的模型是由 [X] 开发的"
    (re.compile(r'我的模型是由[\w\s\-\.一-鿿()（）]+?(?:开发|训练|创建|制作|创造)', re.I),
     f'我的模型是由{PUBLIC_MODEL_NAME}团队开发'),
    # Chinese: "我叫 [X]" — model introducing itself by name
    (re.compile(r'我叫\s*[\w\-\.\s]+?(?:，|。|！|$)', re.I),
     f'我叫{PUBLIC_MODEL_NAME}，'),
    # Chinese: "名为 [X] 的模型"
    (re.compile(r'(?:一个)?名为\s*[\w\-\.\s]+?\s*的(?:模型|大模型)', re.I),
     f'{PUBLIC_MODEL_NAME}'),
    # Chinese: "作为 [X] 模型"
    (re.compile(r'作为(?:一个|一款)\s*(?:AI|人工智能|大语言|语言|对话)?\s*模型', re.I),
     f'作为{PUBLIC_MODEL_NAME}'),
    # "General Language Model" → "General Purpose Language Model"
    (re.compile(r'General Language Model', re.I), 'General Purpose Language Model'),
    # "a large language model trained/developed by [X]"
    (re.compile(r'(?:a\s+)?large language model (?:trained|developed|created) by\s+[\w\s\-\.]+', re.I),
     f'large language model developed by DongLiCao'),
]

CLEAN_PATTERNS = BRAND_PATTERNS + IDENTITY_PATTERNS

# ── Backend Error Detection ───────────────────────────────────────────────────

_BACKEND_ERROR_MARKERS = [
    '服务繁忙', '稍后重试', '请求频繁', '暂时不可用',
    '服务不可用', '系统繁忙', '请求过多', '限流',
    '服务器繁忙', '接口限流', '触发风控', '访问频率',
    '系统维护',
    'rate limit', 'too many requests', 'service unavailable',
    'server is busy', 'try again later', 'overloaded',
]

_ERROR_CONTEXT_PREFIXES = [
    '抱歉', '对不起', '很抱歉', '非常抱歉',
    'sorry', 'unfortunately', 'apolog',
    '当前', '目前', '暂时', '系统',
    'rate limit', 'service', 'server', 'too many',
]

_NOT_ERROR_PREFIXES = [
    'here ', "here's", 'you should', 'you can', 'you need',
    'in order', 'in python', 'in this', 'for example', 'for this',
    'this is', 'this function', 'this method',
    'we can', 'we need', 'we should',
    'it is', 'it works', 'it returns',
    'if you', 'if the',
    'the function', 'the method', 'the code', 'the class',
    'the overloaded', 'the module', 'the api', 'the endpoint',
    '以下', '你可以', '建议', '可以使用', '需要', '首先',
    '关于', '这是', '这个', '我来', '我建议',
]


def _is_backend_error(text: str) -> bool:
    """检测后端返回的错误消息（伪装成正常回答）。
    条件: 短文本 + 含错误关键词 + 不以解释性词语开头。
    """
    if not text:
        return False
    stripped = text.strip()
    if len(stripped) > 200:
        return False
    text_lower = stripped.lower()
    has_marker = any(marker in text_lower for marker in _BACKEND_ERROR_MARKERS)
    if not has_marker:
        return False
    # 以解释性词语开头 → 是技术回答，不是错误（任何长度）
    if any(text_lower.startswith(p) for p in _NOT_ERROR_PREFIXES):
        return False
    # 很短的文本(<=80字符)含错误关键词 → 几乎肯定是错误消息
    if len(stripped) <= 80:
        return True
    # 80-200字符: 以错误上下文词开头 → 是错误消息
    return any(text_lower.startswith(p) for p in _ERROR_CONTEXT_PREFIXES)


def clean_response(text: str, backend_name: str = '') -> str:
    """清洗响应：隐藏底层模型/供应商信息。"""
    if not text or '[ERR]' in text[:15]:
        return ''
    if _is_backend_error(text):
        return ''
    for pattern, repl in CLEAN_PATTERNS:
        text = pattern.sub(repl, text)
    return text


def _clean_brand_only(text: str, backend_name: str = '') -> str:
    """仅做品牌名替换，不做错误检测。用于流式 flush 后的逐 chunk 清洗。"""
    if not text:
        return ''
    for pattern, repl in CLEAN_PATTERNS:
        text = pattern.sub(repl, text)
    return text
