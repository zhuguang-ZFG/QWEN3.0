"""Coding orchestrator context: language detection, tiering, pools, streaming enhance."""

from __future__ import annotations

import os
import re
from collections import defaultdict

import backend_reputation
import intent_templates
import quality_gate
from lima_context import build_context_digest

GUIDE_PATH = os.path.join(os.path.dirname(__file__), "skills", "code", "guide.md")
LANG_GUIDES = {
    "python": os.path.join(os.path.dirname(__file__), "skills", "code", "python.md"),
    "javascript": os.path.join(os.path.dirname(__file__), "skills", "code", "javascript.md"),
    "rust": os.path.join(os.path.dirname(__file__), "skills", "code", "rust.md"),
}
_guide_cache: dict[str, str] = {}

_LANG_SIGNALS = {
    "python": [r"\bdef \w+\(", r"\bimport \w+", r"\.py\b", r"\bpip\b", r"\basync def\b"],
    "javascript": [r"\bconst \w+", r"\brequire\(", r"\.js\b", r"\bnpm\b", r"\.tsx?\b"],
    "rust": [r"\bfn \w+\(", r"\blet mut\b", r"\.rs\b", r"\bcargo\b", r"\bimpl\b"],
    "go": [r"\bfunc \w+\(", r"\bpackage \w+", r"\.go\b", r"\bgo mod\b"],
}

LATENCY_BUDGET = {"simple": 5.0, "standard": 12.0, "complex": 30.0}
MAX_REPAIR_ATTEMPTS = 2

COMPLEX_SIGNALS = [
    r"refactor|重构|redesign|架构",
    r"multi.?file|多文件|across.*files",
    r"debug.*error|排查.*bug|为什么.*报错",
    r"explain.*why|为什么.*这样",
    r"optimize|性能优化|performance",
]

SIMPLE_SIGNALS = [
    r"^.{0,80}$",
    r"import|导入",
    r"fix typo|格式化|format",
    r"what is|是什么|什么意思",
]

POOLS = {
    "fast": ["scnet_qwen30b", "scnet_ds_flash", "scnet_qwen235b",
             "cerebras_gptoss", "groq_gptoss", "mistral_small",
             "groq_gptoss_20b"],
    "coder": ["scnet_ds_flash", "scnet_qwen235b", "scnet_qwen30b",
              "scnet_ds_pro", "github_gpt4o", "github_gpt4o_mini",
              "cf_qwen_coder", "cfai_qwen_coder", "cf_gptoss_120b",
              "cf_deepseek_r1", "cf_qwen3_30b", "cfai_deepseek_r1",
              "cfai_llama70b", "cfai_llama4",
              "cerebras_gptoss", "groq_gptoss", "mistral_small",
              "mistral_pixtral", "mistral_large", "mistral_devstral",
              "github_codestral", "or_gptoss_120b", "cf_kimi_k26",
              "scnet_large_ds_flash",
              "kimi", "kimi_thinking", "kimi_search",
              "ddg_gpt4o_mini", "ddg_gpt5_mini",
              "ddg_claude_haiku_45", "ddg_tinfoil_gptoss_120b"],
    "strong": ["scnet_ds_flash", "scnet_qwen235b", "scnet_ds_pro",
               "scnet_qwen30b", "github_gpt4o", "github_gpt4o_mini",
               "cf_qwen_coder", "cfai_qwen_coder", "cf_gptoss_120b",
               "cf_deepseek_r1", "cf_qwen3_30b", "cfai_deepseek_r1",
               "cfai_llama70b", "cfai_llama4",
               "or_gptoss_120b", "github_codestral", "mistral_large",
               "mistral_devstral", "mistral_pixtral", "cf_kimi_k26",
               "scnet_large_ds_flash",
               "kimi", "kimi_thinking", "kimi_search"],
}

_stats = defaultdict(int)
_stats_lock = __import__("threading").Lock()


def detect_language(query: str, messages: list | None = None) -> str:
    text = query
    if messages:
        text = " ".join(
            m.get("content", "") for m in messages[-3:]
            if isinstance(m.get("content"), str)
        )
    scores = {}
    for lang, patterns in _LANG_SIGNALS.items():
        scores[lang] = sum(1 for p in patterns if re.search(p, text, re.I))
    best = max(scores, key=lambda lang: scores[lang]) if scores else "general"
    return best if scores.get(best, 0) >= 2 else "general"


def load_guide(language: str = "general") -> str:
    if language in _guide_cache:
        return _guide_cache[language]
    path = LANG_GUIDES.get(language, GUIDE_PATH)
    try:
        with open(path, encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        try:
            with open(GUIDE_PATH, encoding="utf-8") as f:
                content = f.read()
        except FileNotFoundError:
            content = ""
    _guide_cache[language] = content
    return content


def extract_error_context(query: str) -> str:
    patterns = [
        (r"(Traceback[\s\S]{0,500}?(?:Error|Exception):.*?)(?=\n\n|\Z)", "Python"),
        (r"(error\[E\d+\]:.*?)(?=\n\n|\Z)", "Rust"),
        (r"(at .*?:\d+:\d+[\s\S]{0,200})", "JavaScript"),
        (r"((?:TypeError|ReferenceError|SyntaxError):.*?)(?=\n|\Z)", "Generic"),
    ]
    for pattern, lang_hint in patterns:
        m = re.search(pattern, query, re.M)
        if m:
            return f"\n[{lang_hint}错误上下文] {m.group(1)[:500]}"
    return ""


def classify_code_tier(query: str, messages: list | None = None) -> str:
    q = query.lower()
    complex_score = sum(1 for p in COMPLEX_SIGNALS if re.search(p, q, re.I))
    if complex_score >= 2:
        return "complex"
    if len(query) > 1500 or (messages and len(messages) > 10):
        return "complex"
    simple_score = sum(1 for p in SIMPLE_SIGNALS if re.search(p, q, re.I))
    if simple_score >= 2 and complex_score == 0:
        return "simple"
    return "standard"


def build_enhanced_query(query: str) -> str:
    enhanced_query = intent_templates.amplify_intent(query)
    error_ctx = extract_error_context(query)
    if error_ctx:
        enhanced_query += error_ctx
    return enhanced_query


def build_system_prompt(query: str, messages: list | None, language: str | None = None) -> str:
    lang = language or detect_language(query, messages)
    guide = load_guide(lang)
    context_digest = build_context_digest(query, messages or [], system_prompt=guide)
    if context_digest:
        guide = f"{guide.rstrip()}\n\n{context_digest}\n"
    return guide


def enhance_context(query: str, messages: list, scenario: str = "") -> dict:
    """Zero-latency pre-stream enhancer for coding paths."""
    if scenario != "coding":
        return {
            "system_prompt": "",
            "enhanced_messages": messages,
            "backend_pool": [],
            "language": "general",
            "tier": "none",
        }

    with _stats_lock:
        _stats["total_enhance"] += 1
        language = detect_language(query, messages)
        _stats[f"lang_{language}"] += 1

    guide = build_system_prompt(query, messages, language=language)
    enhanced_query = build_enhanced_query(query)

    # Session memory recall: inject past conversation context
    memory_context = _recall_session_memory(query)
    if memory_context:
        guide = memory_context + "\n\n" + guide

    tier = classify_code_tier(query, messages)
    with _stats_lock:
        _stats[f"tier_{tier}"] += 1
    pool_name = {"simple": "fast", "standard": "coder", "complex": "strong"}[tier]
    from eval_pool_gate import filter_coding_pool

    ranked_pool = filter_coding_pool(
        backend_reputation.sort_by_reputation(POOLS[pool_name])
    )

    enhanced_msgs = messages.copy()
    if enhanced_query != query and messages:
        enhanced_msgs = messages[:-1] + [{"role": "user", "content": enhanced_query}]

    return {
        "system_prompt": guide,
        "enhanced_messages": enhanced_msgs,
        "backend_pool": ranked_pool,
        "language": language,
        "tier": tier,
    }


def record_streaming_quality(backend: str, response_text: str, query: str) -> None:
    with _stats_lock:
        _stats["total_post_eval"] += 1
        gate = quality_gate.check(response_text, query)
        backend_reputation.record(backend, gate["passed"], "stream")
        _stats[f"gate_{'pass' if gate['passed'] else 'fail'}"] += 1


def get_stats() -> dict:
    with _stats_lock:
        return dict(_stats)


def _recall_session_memory(query: str) -> str:
    """Recall relevant past session memories for a coding query."""
    try:
        from session_memory.store import search_memories_keyword, get_recent_memories
        keywords = _extract_memory_keywords(query)
        matches = []
        for kw in keywords[:5]:
            matches.extend(search_memories_keyword(kw, limit=3))
        if not matches:
            matches = get_recent_memories(limit=3)
        if not matches:
            return ""
        lines = ["[Session Memory — past context]"]
        seen = set()
        for m in matches[:5]:
            content = (getattr(m, "content", "") or str(m))[:150]
            if content not in seen:
                lines.append(f"  - {content}")
                seen.add(content)
        return "\n".join(lines) if len(lines) > 1 else ""
    except (ImportError, Exception):
        return ""


def _extract_memory_keywords(query: str) -> list[str]:
    words = __import__("re").findall(r"\b([a-z]{4,20})\b", query.lower())
    stops = {"this", "that", "with", "from", "have", "when", "will", "would"}
    return [w for w in words if w not in stops][:8]
