"""
code_orchestrator.py — 编程模型塔 V3：上下文工程+容错+自愈+学习
Pipeline: Context Engineering → Intent Amplify → Guided Execute → Quality Gate → Repair
Features: 语言检测、精准注入、信誉分、延迟预算、修复熔断、反馈闭环、监控统计
"""
import os
import re
import time
from collections import defaultdict

import intent_templates
import quality_gate
import backend_reputation
from lima_context import build_context_digest

GUIDE_PATH = os.path.join(os.path.dirname(__file__), "skills", "code", "guide.md")
LANG_GUIDES = {
    "python": os.path.join(os.path.dirname(__file__), "skills", "code", "python.md"),
    "javascript": os.path.join(os.path.dirname(__file__), "skills", "code", "javascript.md"),
    "rust": os.path.join(os.path.dirname(__file__), "skills", "code", "rust.md"),
}
_guide_cache: dict[str, str] = {}

# ── Language Detection ────────────────────────────────────────────────────────

_LANG_SIGNALS = {
    "python": [r"\bdef \w+\(", r"\bimport \w+", r"\.py\b", r"\bpip\b", r"\basync def\b"],
    "javascript": [r"\bconst \w+", r"\brequire\(", r"\.js\b", r"\bnpm\b", r"\.tsx?\b"],
    "rust": [r"\bfn \w+\(", r"\blet mut\b", r"\.rs\b", r"\bcargo\b", r"\bimpl\b"],
    "go": [r"\bfunc \w+\(", r"\bpackage \w+", r"\.go\b", r"\bgo mod\b"],
}


def detect_language(query: str, messages: list = None) -> str:
    text = query
    if messages:
        text = " ".join(m.get("content", "") for m in messages[-3:]
                        if isinstance(m.get("content"), str))
    scores = {}
    for lang, patterns in _LANG_SIGNALS.items():
        scores[lang] = sum(1 for p in patterns if re.search(p, text, re.I))
    best = max(scores, key=scores.get) if scores else "general"
    return best if scores.get(best, 0) >= 2 else "general"


def _load_guide(language: str = "general") -> str:
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


# ── Error Context Extraction ─────────────────────────────────────────────────

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

# ── Latency Budget ───────────────────────────────────────────────────────────
LATENCY_BUDGET = {"simple": 5.0, "standard": 12.0, "complex": 30.0}
MAX_REPAIR_ATTEMPTS = 2


# ── Tier Classification ──────────────────────────────────────────────────────

COMPLEX_SIGNALS = [
    r"refactor|重构|redesign|架构",
    r"multi.?file|多文件|across.*files",
    r"debug.*error|排查.*bug|为什么.*报错",
    r"explain.*why|为什么.*这样",
    r"optimize|性能优化|performance",
]

SIMPLE_SIGNALS = [
    r"^.{0,80}$",  # very short query
    r"import|导入",
    r"fix typo|格式化|format",
    r"what is|是什么|什么意思",
]


def classify_code_tier(query: str, messages: list = None) -> str:
    """分层: simple / standard / complex"""
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


# ── Backend Pools ────────────────────────────────────────────────────────────

POOLS = {
    # 2026-05-22 VPS first-tier eval: direct SCNet models passed coding
    # fixtures from production. Kimi did not pass first-tier criteria yet.
    "fast": ["scnet_qwen30b", "scnet_ds_flash", "scnet_qwen235b",
             "cerebras_gptoss", "groq_gptoss", "mistral_small",
             "groq_gptoss_20b"],
    "coder": ["scnet_ds_flash", "scnet_qwen235b", "scnet_qwen30b",
              "scnet_ds_pro", "github_gpt4o", "github_gpt4o_mini",
              "cerebras_gptoss", "groq_gptoss", "mistral_small",
              "mistral_pixtral", "mistral_large", "mistral_devstral",
              "github_codestral", "or_gptoss_120b", "cf_kimi_k26",
              "scnet_large_ds_flash", "ddg_gpt4o_mini", "ddg_gpt5_mini",
              "ddg_claude_haiku_45", "ddg_tinfoil_gptoss_120b"],
    "strong": ["scnet_ds_flash", "scnet_qwen235b", "scnet_ds_pro",
               "scnet_qwen30b", "github_gpt4o", "github_gpt4o_mini",
               "or_gptoss_120b", "github_codestral", "mistral_large",
               "mistral_devstral", "mistral_pixtral", "cf_kimi_k26",
               "scnet_large_ds_flash", "scnet_large_ds_pro"],
}


# ── Main Pipeline ────────────────────────────────────────────────────────────

def handle(query: str, messages: list, call_fn, max_tokens: int = 4096) -> dict:
    """编程模型塔主入口。返回 {answer, backend, tier, repaired, score}"""
    tier = classify_code_tier(query, messages)
    budget = LATENCY_BUDGET[tier]
    t0 = time.time()

    # Phase 0: Context Engineering — 语言检测 + 精准规范注入
    language = detect_language(query, messages)
    guide = _load_guide(language)
    context_digest = build_context_digest(query, messages, system_prompt=guide)
    if context_digest:
        guide = f"{guide.rstrip()}\n\n{context_digest}\n"

    # Phase 1: Intent Amplification + 错误上下文提取
    enhanced_query = intent_templates.amplify_intent(query)
    error_ctx = extract_error_context(query)
    if error_ctx:
        enhanced_query += error_ctx

    system = guide if guide else ""

    # Phase 2: Execute based on tier (with latency budget)
    if tier == "simple":
        result = _execute_simple(enhanced_query, messages, call_fn, system, max_tokens, t0, budget)
    elif tier == "standard":
        result = _execute_standard(enhanced_query, messages, call_fn, system, max_tokens, t0, budget)
    else:
        result = _execute_complex(enhanced_query, messages, call_fn, system, max_tokens, t0, budget)

    # Phase 3: Feedback loop — update reputation
    if result.get("backend") and result["backend"] != "exhausted":
        passed = result.get("score", 70) >= 70
        backend_reputation.record(result["backend"], passed, f"code_{tier}")

    return result


def _try_backends_ranked(pool_name: str, messages: list, call_fn,
                         system: str, max_tokens: int,
                         t0: float, deadline: float) -> tuple[str, str]:
    """按信誉分排序尝试后端，超时返回空。"""
    pool = POOLS.get(pool_name, [])
    ranked = backend_reputation.sort_by_reputation(pool)
    for backend in ranked:
        if time.time() - t0 > deadline:
            break
        try:
            msgs = messages.copy()
            if system:
                msgs.insert(0, {"role": "system", "content": system})
            answer = call_fn(backend, msgs, max_tokens)
            if answer and len(answer.strip()) > 5:
                return backend, answer
        except Exception:
            continue
    return "", ""


def _execute_simple(query, messages, call_fn, system, max_tokens, t0, budget):
    """Simple 层：Fast 模型直出，不验证。"""
    msgs = _build_msgs(query, messages)
    backend, answer = _try_backends_ranked("fast", msgs, call_fn, system, max_tokens, t0, budget)
    if not answer:
        backend, answer = _try_backends_ranked("coder", msgs, call_fn, system, max_tokens, t0, budget)
    return {"answer": answer, "backend": backend, "tier": "simple",
            "repaired": False, "score": 80 if answer else 0}


def _execute_standard(query, messages, call_fn, system, max_tokens, t0, budget):
    """Standard 层：Coder + Quality Gate + 修复熔断。"""
    msgs = _build_msgs(query, messages)
    backend, answer = _try_backends_ranked("coder", msgs, call_fn, system, max_tokens, t0, budget * 0.5)
    if not answer:
        return {"answer": "", "backend": "exhausted", "tier": "standard",
                "repaired": False, "score": 0}

    gate = quality_gate.check(answer, query)
    if gate["passed"]:
        backend_reputation.record(backend, True, "code_standard")
        return {"answer": answer, "backend": backend, "tier": "standard",
                "repaired": False, "score": gate["score"]}

    # 质量不达标 → 修复熔断机制
    backend_reputation.record(backend, False, "code_standard")
    remaining = budget - (time.time() - t0)
    if remaining < 3.0:
        return {"answer": answer, "backend": backend, "tier": "standard",
                "repaired": False, "score": gate["score"]}

    repaired = _repair_with_breaker(query, answer, gate["reasons"],
                                     msgs, call_fn, system, max_tokens, t0, budget)
    if repaired:
        return {"answer": repaired[1], "backend": repaired[0], "tier": "standard",
                "repaired": True, "score": repaired[2]}

    return {"answer": answer, "backend": backend, "tier": "standard",
            "repaired": False, "score": gate["score"]}


def _execute_complex(query, messages, call_fn, system, max_tokens, t0, budget):
    """Complex 层：Strong 模型优先，也过质量门。"""
    msgs = _build_msgs(query, messages)

    # Strong 模型也验证（Step 11）
    backend, answer = _try_backends_ranked("strong", msgs, call_fn, system, max_tokens, t0, budget * 0.7)
    if answer:
        gate = quality_gate.check(answer, query)
        if gate["passed"]:
            backend_reputation.record(backend, True, "code_complex")
            return {"answer": answer, "backend": backend, "tier": "complex",
                    "repaired": False, "score": gate["score"]}
        else:
            backend_reputation.record(backend, False, "code_complex")

    # Strong 失败 → Coder fallback
    remaining = budget - (time.time() - t0)
    if remaining > 3.0:
        backend, answer = _try_backends_ranked("coder", msgs, call_fn, system, max_tokens, t0, budget)
        if answer:
            return {"answer": answer, "backend": backend, "tier": "complex",
                    "repaired": False, "score": quality_gate.check(answer, query)["score"]}

    return {"answer": answer or "", "backend": backend or "exhausted",
            "tier": "complex", "repaired": False, "score": 0}


def _repair_with_breaker(query, bad_answer, reasons, messages,
                          call_fn, system, max_tokens, t0, budget):
    """修复熔断：最多 2 次，每次换后端，策略切换。"""
    strong_pool = POOLS["strong"][:]

    for attempt in range(MAX_REPAIR_ATTEMPTS):
        remaining = budget - (time.time() - t0)
        if remaining < 2.0 or not strong_pool:
            break

        backend_to_use = strong_pool.pop(0)

        if attempt == 0:
            # 策略 1: 定向修复
            repair_prompt = (
                f"以下代码回复存在问题: {', '.join(reasons)}\n\n"
                f"原始问题: {query}\n\n"
                f"有问题的回复:\n{bad_answer[:1500]}\n\n"
                f"请修复上述问题，直接给出正确的完整代码回复。"
            )
        else:
            # 策略 2: 从零重写（不基于 bad_answer）
            repair_prompt = query

        repair_msgs = [{"role": "user", "content": repair_prompt}]
        try:
            msgs = repair_msgs.copy()
            if system:
                msgs.insert(0, {"role": "system", "content": system})
            answer = call_fn(backend_to_use, msgs, max_tokens)
            if answer and len(answer.strip()) > 10:
                gate = quality_gate.check(answer, query)
                if gate["passed"]:
                    backend_reputation.record(backend_to_use, True, "code_repair")
                    return (backend_to_use, answer, gate["score"])
                backend_reputation.record(backend_to_use, False, "code_repair")
        except Exception:
            continue

    return None


def _build_msgs(query, messages):
    """构建消息列表，用增强后的 query 替换最后一条用户消息。"""
    if len(messages) > 1:
        return messages[:-1] + [{"role": "user", "content": query}]
    return [{"role": "user", "content": query}]


# ── Streaming 前置增强器 (方案C: 零延迟，不调模型) ────────────────────────────

# 监控计数器
_stats = defaultdict(int)


def enhance_context(query: str, messages: list, scenario: str = "") -> dict:
    """前置增强器：零延迟，用于 streaming 路径。
    返回 {system_prompt, enhanced_messages, backend_pool, language, tier}
    """
    if scenario != "coding":
        return {"system_prompt": "", "enhanced_messages": messages,
                "backend_pool": [], "language": "general", "tier": "none"}

    _stats["total_enhance"] += 1

    # 1. 语言检测
    language = detect_language(query, messages)
    _stats[f"lang_{language}"] += 1

    # 2. 精准规范注入
    guide = _load_guide(language)
    context_digest = build_context_digest(query, messages, system_prompt=guide)
    if context_digest:
        guide = f"{guide.rstrip()}\n\n{context_digest}\n"

    # 3. 意图增强
    enhanced_query = intent_templates.amplify_intent(query)
    error_ctx = extract_error_context(query)
    if error_ctx:
        enhanced_query += error_ctx

    # 4. 按信誉分选最优后端池
    tier = classify_code_tier(query, messages)
    _stats[f"tier_{tier}"] += 1
    pool_name = {"simple": "fast", "standard": "coder", "complex": "strong"}[tier]
    ranked_pool = backend_reputation.sort_by_reputation(POOLS[pool_name])

    # 5. 构建增强后的 messages
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


def record_streaming_quality(backend: str, response_text: str, query: str):
    """后置评估器：streaming 完成后异步调用，更新信誉分。"""
    _stats["total_post_eval"] += 1
    gate = quality_gate.check(response_text, query)
    backend_reputation.record(backend, gate["passed"], "stream")
    _stats[f"gate_{'pass' if gate['passed'] else 'fail'}"] += 1


def get_stats() -> dict:
    """返回监控统计。"""
    return dict(_stats)
