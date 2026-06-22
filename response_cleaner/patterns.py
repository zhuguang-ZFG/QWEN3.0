"""Brand and identity replacement patterns for response cleaning."""

import re

import brand_config
from backends_constants import PUBLIC_MODEL_NAME

# Brand names to replace with LiMa (sorted by priority: specific → general)
_BRANDS = [
    # Anthropic ecosystem
    "claude",
    "longcat",
    # Chinese LLM companies & models
    "deepseek",
    "深度求索",
    "glm",
    "chatglm",
    "智谱",
    "qwen",
    "通义千问",
    "ernie",
    "文心一言",
    "文心",
    "hunyuan",
    "混元",
    "doubao",
    "豆包",
    "kimi",
    "月之暗面",
    "minimax",
    "海螺",
    "metaso",
    "秘塔",
    "step",
    "阶跃星辰",
    "spark",
    "讯飞",
    "星火",
    "baichuan",
    "百川",
    "yi",
    "yi-series",
    "yi-model",
    "零一万物",
    # Western providers
    "openai",
    "chatgpt",
    "anthropic",
    "google",
    "gemini",
    "gemma",
    "mistral",
    "codestral",
    "pixtral",
    "devstral",
    "nvidia",
    "nemotron",
    "llama",
    "meta-ai",
    "meta ai",
    "phi-3",
    "phi-4",
    "cohere",
    "command-a",
    "command-r",
    "cerebras",
    "groq",
    "cloudflare",
    "sambanova",
    "deepinfra",
    "fireworks",
    "together ai",
    "together-ai",
    "togetherai",
    "ai21",
    "jamba",
    # Zero-key / community providers
    "pollinations",
    "ovhcloud",
    "hermes",
    "naga ai",
    "naga-ai",
    "freetheai",
    "zukijourney",
    "featherless",
    "glhf",
    "agentrouter",
    "llm7",
    "chatubi",
    "uncloseai",
    # Chinese cloud providers
    "siliconflow",
    "硅基流动",
    "volcengine",
    "火山引擎",
    "alibaba",
    "aliyun",
    "dashscope",
    "阿里云",
    "baidu",
    "百度",
    "tencent",
    "腾讯",
    "chinamobile",
    "中国移动",
    "iflytek",
    # Generic model descriptors
    "gpt-3",
    "gpt-4",
    "gpt-5",
    "gpt-oss",
    "openrouter",
]


def _build_brand_re(brand: str) -> re.Pattern:
    """Build a case-insensitive regex for a single brand name."""
    escaped = re.escape(brand)
    if brand[0].isascii():
        # Use ASCII-only boundary and suffix to avoid eating CJK characters
        return re.compile(rf"(?<![a-zA-Z0-9_]){escaped}[a-zA-Z0-9_\-\.\[\]\/\:]*", re.I)
    # CJK: match brand name literally, don't extend into surrounding text
    return re.compile(rf"{escaped}", re.I)


BRAND_PATTERNS = [(_build_brand_re(b), PUBLIC_MODEL_NAME) for b in _BRANDS]

IDENTITY_PATTERNS = [
    # English: "I am [X], made by [Y]" — but don't match "I am LiMa"
    (
        re.compile(r"\bI (?:am|'m) (?:an? )?(?:AI (?:language )?model|large language model)(?!.*LiMa)", re.I),
        "I am an AI language model",
    ),
    # English: "developed/created/trained by [Company]"
    (re.compile(r"(?:developed|created|trained|made|built|powered) by\s+[\w\s\-\.]+", re.I), f"developed by {brand_config.COMPANY_NAME_EN}"),
    # Chinese: "我是 [X]的[AI/语言]模型"
    (
        re.compile(
            r"我是(?:由|一个|一款)[\w\s\-\.一-鿿()（）]+?(?:开发|训练|创建|制作|创造|推出|提供)的(?:\s*(?:AI|人工智能|大语言|语言|对话))?\s*模型",
            re.I,
        ),
        f"我是{PUBLIC_MODEL_NAME}",
    ),
    # Chinese: "我是一个 [AI/语言/大] 模型"
    (re.compile(r"我是(?:一个|一款)\s*(?:AI|人工智能|大语言|语言|对话)\s*模型", re.I), f"我是{PUBLIC_MODEL_NAME}"),
    # Chinese: "我的模型是由 [X] 开发的"
    (
        re.compile(r"我的模型是由[\w\s\-\.一-鿿()（）]+?(?:开发|训练|创建|制作|创造)", re.I),
        f"我的模型是由{PUBLIC_MODEL_NAME}团队开发",
    ),
    # Chinese: "我叫 [X]"
    (re.compile(r"我叫\s*[\w\-\.\s]+?(?:，|。|！|$)", re.I), f"我叫{PUBLIC_MODEL_NAME}，"),
    # Chinese: "名为 [X] 的模型"
    (re.compile(r"(?:一个)?名为\s*[\w\-\.\s]+?\s*的(?:模型|大模型)", re.I), f"{PUBLIC_MODEL_NAME}"),
    # Chinese: "作为 [X] 模型"
    (re.compile(r"作为(?:一个|一款)\s*(?:AI|人工智能|大语言|语言|对话)?\s*模型", re.I), f"作为{PUBLIC_MODEL_NAME}"),
    # "General Language Model" → "General Purpose Language Model"
    (re.compile(r"General Language Model", re.I), "General Purpose Language Model"),
    # "a large language model trained/developed by [X]"
    (
        re.compile(r"(?:a\s+)?large language model (?:trained|developed|created) by\s+[\w\s\-\.]+", re.I),
        f"large language model developed by {brand_config.COMPANY_NAME_EN}",
    ),
    # English: "As Claude/GPT/Gemini, ..."
    (
        re.compile(
            r"\bAs\s+(?:Claude|Gemini|GPT(?:-[\d\.]+)?|ChatGPT|Qwen|DeepSeek|Llama|Kimi|"
            r"Codestral|Mistral|Gemma|ERNIE|Doubao|GLM|Meta\s*AI)\b",
            re.I,
        ),
        f"As {PUBLIC_MODEL_NAME}",
    ),
    # English: "This is Claude/GPT/..."
    (
        re.compile(r"\bThis\s+is\s+(?:Claude|Gemini|GPT(?:-[\d\.]+)?|ChatGPT|Qwen|DeepSeek|Llama|Kimi)\b", re.I),
        f"This is {PUBLIC_MODEL_NAME}",
    ),
    # English: "Claude/GPT here"
    (
        re.compile(r"\b(?:Claude|Gemini|GPT(?:-[\d\.]+)?|ChatGPT|Qwen|DeepSeek|Llama|Kimi)\s+here\b", re.I),
        f"{PUBLIC_MODEL_NAME} here",
    ),
]

CLEAN_PATTERNS = BRAND_PATTERNS + IDENTITY_PATTERNS
