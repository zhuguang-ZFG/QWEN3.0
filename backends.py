"""LiMa backend facade: registry, constants, and detection helpers."""
import sys

from backends_constants import (
    CODE_CAPABLE_BACKENDS,
    GFW_BACKENDS,
    IDE_SOURCES,
    KEY_POOL_PREFIXES,
    PUBLIC_MODEL_NAME,
    STRONG_MODELS,
    THINKING_BACKENDS,
    VISION_BACKENDS,
    VISION_SYSTEM_PROMPT,
    WEAK_BACKENDS,
)
from backends_registry import BACKENDS, DISABLED_HOST_DEPENDENT_BACKENDS, LM_URL

# -- Backend enable/disable state (default: enabled) --
_backend_enabled: dict[str, bool] = {}

def is_enabled(name: str) -> bool:
    return _backend_enabled.get(name, True)

def set_enabled(name: str, enabled: bool) -> None:
    _backend_enabled[name] = enabled

def get_configured() -> list:
    return [k for k, v in BACKENDS.items() if v.get("key") and k != "local"]

# -- Auto-detection: vendor, tier, protocol, capabilities --

# Vendor detection mapping: (pattern, vendor_name)
# Order matters: more specific patterns first
_VENDOR_PATTERNS = [
    ('localhost', 'Local (Ollama)'),
    ('127.0.0.1', 'Local (Ollama)'),
    ('trycloudflare.com', 'Local (Ollama)'),
    ('ddg.zhuguang', 'DuckDuckGo AI'),
    ('tele.zhuguang', 'lza6 Workers'),
    ('assist.zhuguang', 'lza6 Workers'),
    ('vision.zhuguang', 'lza6 Workers'),
    ('stock.zhuguang', 'StockAI'),
    ('llm.zhuguang', 'TheOldLLM'),
    ('models.inference.ai.azure.com', 'GitHub Models'),
    ('generativelanguage.googleapis.com', 'Google'),
    ('mistral.ai', 'Mistral'),
    ('codestral.mistral', 'Mistral'),
    ('longcat', 'LongCat'),
    ('nvidia', 'NVIDIA'),
    ('openrouter', 'OpenRouter'),
    ('deepseek', 'DeepSeek'),
    ('chinamobile', 'China Mobile'),
    ('groq.com', 'Groq'),
    ('cerebras', 'Cerebras'),
    ('cloudflare.com', 'Cloudflare'),
    ('ai.gitee.com', 'Gitee AI'),
    ('bigmodel.cn', 'Zhipu'),
    ('siliconflow.cn', 'SiliconFlow'),
    ('baidubce.com', 'Baidu'),
    ('volces.com', 'Volcengine'),
    ('aliyuncs.com', 'Alibaba'),
    ('tencent', 'Tencent'),
    ('hunyuan', 'Tencent'),
    ('unturf.com', 'UncloseAI'),
    ('ch.at', 'ChatUbi'),
    ('llm7.io', 'LLM7'),
    ('pollinations', 'Pollinations'),
    ('opencode.ai', 'OpenCode Zen'),
    ('fireworks.ai', 'Fireworks AI'),
    ('ovh.net', 'OVHcloud'),
    ('cohere.com', 'Cohere'),
    ('sambanova.ai', 'SambaNova'),
    ('deepinfra.com', 'DeepInfra'),
]


def detect_vendor(url: str) -> str:
    """Detect backend vendor from URL using pattern matching.

    Complexity: O(n) where n = number of patterns (~40).
    Previously: cyclomatic complexity 34 (one if per vendor).
    Now: cyclomatic complexity 2 (for loop + return).
    """
    u = url.lower()
    for pattern, vendor in _VENDOR_PATTERNS:
        if pattern in u:
            return vendor
    return 'Unknown'

def detect_tier(url: str, name: str = "") -> str:
    u = url.lower()
    if 'localhost' in u or '127.0.0.1' in u or 'trycloudflare.com' in u: return 'L0 Local'
    if 'longcat' in u or 'chinamobile' in u: return 'L1 Free Unlimited'
    if 'nvidia' in u: return 'L2 Free Quota'
    if 'openrouter' in u: return 'L3 Free Limited'
    if 'deepseek.com' in u: return 'L4 Paid'
    if 'opencode.ai' in u or 'ovh.net' in u: return 'L1 Free Unlimited'
    if 'fireworks.ai' in u or 'sambanova.ai' in u or 'deepinfra.com' in u: return 'L3 Free Limited'
    if 'cohere.com' in u: return 'L2 Free Quota'
    return 'L3 Free Limited'

def detect_protocol(fmt: str) -> str:
    return 'Anthropic' if fmt == 'anthropic' else 'OpenAI'

def detect_caps(name: str, cfg: dict = None) -> list:
    if cfg and cfg.get("caps"):
        explicit = set(cfg["caps"])
    else:
        explicit = set()
    caps = list(explicit)
    if name in CODE_CAPABLE_BACKENDS or "coder" in name or "codestral" in name:
        if "code" not in caps:
            caps.append("code")
    if name in VISION_BACKENDS:
        if "vision" not in caps:
            caps.append('vision')
    if 'thinking' in name or 'r1' in name:
        if "deep_reasoning" not in caps:
            caps.append('deep_reasoning')
    if not caps:
        caps.append('text_only')
    return caps


def backend_has_capability(name: str, capability: str, cfg: dict = None) -> bool:
    """Return whether a backend has a normalized capability."""
    resolved = cfg or BACKENDS.get(name) or DISABLED_HOST_DEPENDENT_BACKENDS.get(name, {})
    return capability in detect_caps(name, resolved)


def is_weak_backend(name: str) -> bool:
    return name in WEAK_BACKENDS


def first_backend_with_capability(names: list[str], capability: str) -> str:
    for name in names:
        if backend_has_capability(name, capability):
            return name
    return ""


def infer_key_pool_provider(name: str, cfg: dict = None) -> str:
    cfg = cfg or BACKENDS.get(name, {})
    if cfg.get("key_pool"):
        return cfg["key_pool"]
    for prefix, provider in KEY_POOL_PREFIXES.items():
        if name.startswith(prefix):
            return provider
    return ""

# -- Startup validation --
def startup_check():
    configured = get_configured()
    if configured:
        print(f'[LiMa] {len(configured)} backends configured', file=sys.stderr)
    if not configured:
        print('[LiMa] WARNING: No backends have API keys!', file=sys.stderr)

# Auto-run check on import
startup_check()
