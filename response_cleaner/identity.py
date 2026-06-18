"""Identity leak detection and brand/identity replacement helpers."""

import re

from response_cleaner.patterns import CLEAN_PATTERNS

_KNOWN_MODEL_BRANDS = (
    r"claude|gemini|gpt(?:-[\d\.]+)?|chatgpt|qwen|deepseek|llama|kimi|codestral|"
    r"mistral|gemma|ernie|doubao|glm|meta\s*ai|通义|文心|豆包"
)


def _looks_like_self_identity(text: str) -> bool:
    """Return True if the text appears to be a model introducing itself."""
    if not text:
        return False
    lowered = text.lower()
    return bool(
        re.search(
            r"\b(i\s+am|i'm|my\s+model|as\s+an?\s+(?:ai\s+)?(?:language\s+)?model)\b",
            lowered,
        )
        or re.search(rf"\bas\s+(?:an?\s+)?(?:{_KNOWN_MODEL_BRANDS})\b", lowered)
        or re.search(rf"\bthis\s+is\s+(?:{_KNOWN_MODEL_BRANDS})\b", lowered)
        or re.search(rf"\b(?:{_KNOWN_MODEL_BRANDS})\s+here\b", lowered)
        or (
            re.search(r"\b(?:made|built|created|developed|trained|powered)\s+by\b", lowered)
            and re.search(r"\b(i\s+am|i'm|model|assistant)\b", lowered)
        )
        or any(marker in text for marker in ("我是", "我叫", "我的模型", "作为"))
    )


def apply_identity_cleaning(text: str) -> str:
    """Apply brand + identity pattern replacements without backend-error stripping."""
    if not text:
        return ""
    cleaned = text
    for pattern, repl in CLEAN_PATTERNS:
        cleaned = pattern.sub(repl, cleaned)
    return cleaned.strip()
