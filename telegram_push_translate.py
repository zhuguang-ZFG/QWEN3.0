"""Optional translation for Telegram push notifications (TG-GH-7)."""

from __future__ import annotations

import logging
import os
import re

_log = logging.getLogger(__name__)
logger = logging.getLogger(__name__)

_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")
# Keep push translation off chat_fast / vision pools (GFL-2 RPM isolation).
_DEFAULT_LLM_BACKENDS = ("scnet_qwen30b", "cf_llama70b")
_RESERVED_ROUTING_BACKENDS = frozenset({"google_flash_lite", "google_flash", "cf_vision"})


def push_translate_enabled() -> bool:
    return os.environ.get("TELEGRAM_PUSH_TRANSLATE", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def push_translate_engine() -> str:
    return os.environ.get("TELEGRAM_PUSH_TRANSLATE_ENGINE", "llm").strip().lower() or "llm"


def push_translate_target() -> str:
    return os.environ.get("TELEGRAM_PUSH_TRANSLATE_LANG", "zh-CN").strip() or "zh-CN"


def push_translate_backends() -> tuple[str, ...]:
    raw = os.environ.get("TELEGRAM_PUSH_TRANSLATE_BACKEND", "").strip()
    if raw:
        parts = tuple(b.strip() for b in raw.split(",") if b.strip())
        candidates = parts or _DEFAULT_LLM_BACKENDS
    else:
        candidates = _DEFAULT_LLM_BACKENDS
    filtered = tuple(b for b in candidates if b not in _RESERVED_ROUTING_BACKENDS)
    return filtered or _DEFAULT_LLM_BACKENDS


_SKIP_TRANSLATE_MARKERS = (
    "LiMa Daily",
    "Backends:",
    "Budget:",
    "Inventory 7d:",
    "Requests today:",
    "GitHub 24h:",
    "Gitee 24h:",
)


def mostly_chinese(text: str) -> bool:
    sample = (text or "")[:800]
    if not sample.strip():
        return True
    cjk = len(_CJK_RE.findall(sample))
    letters = sum(1 for ch in sample if ch.isalpha())
    if letters == 0:
        return cjk > 0
    return cjk / max(letters, 1) >= 0.25


def should_skip_translate(text: str) -> bool:
    body = (text or "").strip()
    if not body:
        return True
    if mostly_chinese(body):
        return True
    return any(marker in body for marker in _SKIP_TRANSLATE_MARKERS)


def _lang_label(target: str) -> str:
    if target.startswith("zh"):
        return "简体中文"
    return target


def _backend_usable(backend: str) -> bool:
    from backends import BACKENDS

    if backend not in BACKENDS:
        return False
    try:
        import budget_manager
        import health_tracker
    except ImportError:
        return True
    if health_tracker.is_cooled_down(backend):
        return False
    return budget_manager.is_budget_available(backend)


def _translate_via_llm(text: str, *, target: str) -> str | None:
    chunk = text.strip()[:1200]
    if not chunk:
        return None

    lang = _lang_label(target)
    system_prompt = (
        f"Translate the following operator notification into {lang}. "
        "Keep repository names, branch names, commit SHAs, numbers, URLs, "
        "and text inside backticks unchanged. "
        "Output only the translation with no preamble or quotes."
    )
    messages = [{"role": "user", "content": chunk}]

    import http_caller

    for backend in push_translate_backends():
        if not _backend_usable(backend):
            continue
        try:
            answer = http_caller.call_api(
                backend,
                messages,
                max_tokens=512,
                system_prompt=system_prompt,
            )
        except Exception as exc:
            logger.debug("llm push translate failed backend=%s", backend, exc_info=True)
            continue
        cleaned = (answer or "").strip()
        if cleaned and not cleaned.startswith("[ERR]"):
            return cleaned
    return None


def _translate_via_mymemory(text: str, *, target: str) -> str | None:
    from channel_gateway.public_apis import translate_text_only

    return translate_text_only(text.strip()[:500], target=target)


def _translate_chunk(text: str, *, target: str) -> str | None:
    engine = push_translate_engine()
    if engine == "mymemory":
        return _translate_via_mymemory(text, target=target)
    translated = _translate_via_llm(text, target=target)
    if translated:
        return translated
    return _translate_via_mymemory(text, target=target)


def _append_translation(body: str, translated: str) -> str:
    if len(body) <= 420:
        return f"{body}\n\n【译】{translated}"
    return f"{body[:420]}…\n\n【译】{translated}"


def translate_push_text(text: str, *, target: str | None = None) -> str:
    """Translate outbound push text when enabled; skip if already Chinese."""
    body = (text or "").strip()
    if not body or not push_translate_enabled() or should_skip_translate(body):
        return text

    lang = target or push_translate_target()
    translated = _translate_chunk(body, target=lang)
    if not translated:
        return text
    return _append_translation(body, translated)
