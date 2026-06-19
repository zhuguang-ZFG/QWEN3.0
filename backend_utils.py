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
_VENDOR_HINTS: tuple[tuple[str, str], ...] = (
    ("longcat", "LongCat"),
    ("nvidia", "NVIDIA"),
    ("openrouter", "OpenRouter"),
    ("deepseek", "DeepSeek"),
    ("chinamobile", "China Mobile"),
    ("localhost", "Local (Ollama)"),
    ("127.0.0.1", "Local (Ollama)"),
    ("trycloudflare.com", "Local (Ollama)"),
    ("ddg.zhuguang", "DuckDuckGo AI"),
    ("tele.zhuguang", "lza6 Workers"),
    ("assist.zhuguang", "lza6 Workers"),
    ("vision.zhuguang", "lza6 Workers"),
    ("stock.zhuguang", "StockAI"),
    ("llm.zhuguang", "TheOldLLM"),
    ("groq.com", "Groq"),
    ("cerebras", "Cerebras"),
    ("models.inference.ai.azure.com", "GitHub Models"),
    ("generativelanguage.googleapis.com", "Google"),
    ("cloudflare.com", "Cloudflare"),
    ("ai.gitee.com", "Gitee AI"),
    ("mistral.ai", "Mistral"),
    ("codestral.mistral", "Mistral"),
    ("bigmodel.cn", "Zhipu"),
    ("siliconflow.cn", "SiliconFlow"),
    ("baidubce.com", "Baidu"),
    ("volces.com", "Volcengine"),
    ("aliyuncs.com", "Alibaba"),
    ("tencent", "Tencent"),
    ("hunyuan", "Tencent"),
    ("unturf.com", "UncloseAI"),
    ("ch.at", "ChatUbi"),
    ("llm7.io", "LLM7"),
    ("pollinations", "Pollinations"),
    ("fireworks.ai", "Fireworks AI"),
    ("ovh.net", "OVHcloud"),
    ("cohere.com", "Cohere"),
    ("sambanova.ai", "SambaNova"),
    ("deepinfra.com", "DeepInfra"),
)


def _match_vendor(url: str) -> str | None:
    for hint, vendor in _VENDOR_HINTS:
        if hint in url:
            return vendor
    return None


def detect_vendor(url: str) -> str:
    return _match_vendor(url.lower()) or "Unknown"


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
