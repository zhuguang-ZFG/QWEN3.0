"""LiMa backend inspection and state helpers."""

from backends_constants import (
    CODE_CAPABLE_BACKENDS,
    KEY_POOL_PREFIXES,
    VISION_BACKENDS,
    WEAK_BACKENDS,
)
from backends_registry import BACKENDS

# -- Backend enable/disable state (default: enabled) --
_backend_enabled: dict[str, bool] = {}


def is_enabled(name: str) -> bool:
    return _backend_enabled.get(name, True)


def set_enabled(name: str, enabled: bool) -> None:
    _backend_enabled[name] = enabled


def get_configured() -> list[str]:
    return [k for k, v in BACKENDS.items() if v.get("key") and k != "local"]


# -- Auto-detection: vendor, tier, protocol, capabilities --
def detect_vendor(url: str) -> str:
    u = url.lower()
    if "longcat" in u:
        return "LongCat"
    if "nvidia" in u:
        return "NVIDIA"
    if "openrouter" in u:
        return "OpenRouter"
    if "deepseek" in u:
        return "DeepSeek"
    if "chinamobile" in u:
        return "China Mobile"
    if "localhost" in u or "127.0.0.1" in u or "trycloudflare.com" in u:
        return "Local (Ollama)"
    if "ddg.zhuguang" in u:
        return "DuckDuckGo AI"
    if "tele.zhuguang" in u or "assist.zhuguang" in u or "vision.zhuguang" in u:
        return "lza6 Workers"
    if "stock.zhuguang" in u:
        return "StockAI"
    if "llm.zhuguang" in u:
        return "TheOldLLM"
    if "groq.com" in u:
        return "Groq"
    if "cerebras" in u:
        return "Cerebras"
    if "models.inference.ai.azure.com" in u:
        return "GitHub Models"
    if "generativelanguage.googleapis.com" in u:
        return "Google"
    if "cloudflare.com" in u:
        return "Cloudflare"
    if "ai.gitee.com" in u:
        return "Gitee AI"
    if "mistral.ai" in u or "codestral.mistral" in u:
        return "Mistral"
    if "bigmodel.cn" in u:
        return "Zhipu"
    if "siliconflow.cn" in u:
        return "SiliconFlow"
    if "baidubce.com" in u:
        return "Baidu"
    if "volces.com" in u:
        return "Volcengine"
    if "aliyuncs.com" in u:
        return "Alibaba"
    if "tencent" in u or "hunyuan" in u:
        return "Tencent"
    if "unturf.com" in u:
        return "UncloseAI"
    if "ch.at" in u:
        return "ChatUbi"
    if "llm7.io" in u:
        return "LLM7"
    if "pollinations" in u:
        return "Pollinations"
    if "fireworks.ai" in u:
        return "Fireworks AI"
    if "ovh.net" in u:
        return "OVHcloud"
    if "cohere.com" in u:
        return "Cohere"
    if "sambanova.ai" in u:
        return "SambaNova"
    if "deepinfra.com" in u:
        return "DeepInfra"
    return "Unknown"


def detect_tier(url: str, name: str = "") -> str:
    u = url.lower()
    if "localhost" in u or "127.0.0.1" in u or "trycloudflare.com" in u:
        return "L0 Local"
    if "longcat" in u or "chinamobile" in u:
        return "L1 Free Unlimited"
    if "nvidia" in u:
        return "L2 Free Quota"
    if "openrouter" in u:
        return "L3 Free Limited"
    if "deepseek.com" in u:
        return "L4 Paid"
    if "ovh.net" in u:
        return "L1 Free Unlimited"
    if "fireworks.ai" in u or "sambanova.ai" in u or "deepinfra.com" in u:
        return "L3 Free Limited"
    if "cohere.com" in u:
        return "L2 Free Quota"
    return "L3 Free Limited"


def detect_protocol(fmt: str) -> str:
    return "Anthropic" if fmt == "anthropic" else "OpenAI"


def detect_caps(name: str, cfg: dict | None = None) -> list[str]:
    explicit = set(cfg["caps"]) if cfg and cfg.get("caps") else set()
    caps = list(explicit)
    if name in CODE_CAPABLE_BACKENDS or "coder" in name or "codestral" in name:
        if "code" not in caps:
            caps.append("code")
    if name in VISION_BACKENDS:
        if "vision" not in caps:
            caps.append("vision")
    if "thinking" in name or "r1" in name:
        if "deep_reasoning" not in caps:
            caps.append("deep_reasoning")
    if not caps:
        caps.append("text_only")
    return caps


def backend_has_capability(name: str, capability: str, cfg: dict | None = None) -> bool:
    """Return whether a backend has a normalized capability."""
    return capability in detect_caps(name, cfg or BACKENDS.get(name, {}))


def is_weak_backend(name: str) -> bool:
    return name in WEAK_BACKENDS


def first_backend_with_capability(names: list[str], capability: str) -> str:
    for name in names:
        if backend_has_capability(name, capability):
            return name
    return ""


def infer_key_pool_provider(name: str, cfg: dict | None = None) -> str:
    cfg = cfg or BACKENDS.get(name, {})
    if cfg.get("key_pool"):
        return cfg["key_pool"]
    for prefix, provider in KEY_POOL_PREFIXES.items():
        if name.startswith(prefix):
            return provider
    return ""
