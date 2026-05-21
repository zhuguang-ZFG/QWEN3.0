"""
code_orchestrator.py — 编程模型塔：强模型带动弱模型
Pipeline: Intent Amplify → Guided Execute → Quality Gate → Repair
"""
import os
import re
import time

import intent_templates
import quality_gate

GUIDE_PATH = os.path.join(os.path.dirname(__file__), "skills", "code", "guide.md")
_guide_cache = None


def _load_guide() -> str:
    global _guide_cache
    if _guide_cache is None:
        try:
            with open(GUIDE_PATH, encoding="utf-8") as f:
                _guide_cache = f.read()
        except FileNotFoundError:
            _guide_cache = ""
    return _guide_cache


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
    "fast": ["groq_gptoss", "cerebras_gptoss", "groq_llama4", "longcat_lite"],
    "coder": ["cf_qwen_coder", "mistral_codestral", "nvidia_qwen_coder", "groq_llama70b"],
    "strong": ["cf_deepseek_r1", "github_gpt4o", "sambanova_ds_v3"],
}


# ── Main Pipeline ────────────────────────────────────────────────────────────

def handle(query: str, messages: list, call_fn, max_tokens: int = 4096) -> dict:
    """编程模型塔主入口。返回 {answer, backend, tier, repaired}"""
    tier = classify_code_tier(query, messages)
    guide = _load_guide()

    # Phase 1: Intent Amplification
    enhanced_query = intent_templates.amplify_intent(query)

    # Build system prompt with coding guide
    system = guide if guide else ""

    # Phase 2: Execute based on tier
    if tier == "simple":
        return _execute_simple(enhanced_query, messages, call_fn, system, max_tokens)
    elif tier == "standard":
        return _execute_standard(enhanced_query, messages, call_fn, system, max_tokens)
    else:
        return _execute_complex(enhanced_query, messages, call_fn, system, max_tokens)


def _try_backends(pool_name: str, messages: list, call_fn,
                  system: str, max_tokens: int) -> tuple[str, str]:
    """尝试池中后端，返回 (backend, answer)。全失败返回 ('', '')。"""
    for backend in POOLS.get(pool_name, []):
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


def _execute_simple(query: str, messages: list, call_fn,
                    system: str, max_tokens: int) -> dict:
    """Simple 层：Fast 模型直出，不验证。"""
    msgs = [{"role": "user", "content": query}]
    if len(messages) > 1:
        msgs = messages[:-1] + [{"role": "user", "content": query}]
    backend, answer = _try_backends("fast", msgs, call_fn, system, max_tokens)
    if not answer:
        backend, answer = _try_backends("coder", msgs, call_fn, system, max_tokens)
    return {"answer": answer, "backend": backend, "tier": "simple", "repaired": False}


def _execute_standard(query: str, messages: list, call_fn,
                      system: str, max_tokens: int) -> dict:
    """Standard 层：Coder 生成 + Quality Gate + 可能修复。"""
    msgs = [{"role": "user", "content": query}]
    if len(messages) > 1:
        msgs = messages[:-1] + [{"role": "user", "content": query}]
    backend, answer = _try_backends("coder", msgs, call_fn, system, max_tokens)
    if not answer:
        return {"answer": "", "backend": "exhausted", "tier": "standard", "repaired": False}

    # Quality Gate
    gate = quality_gate.check(answer, query)
    if gate["passed"]:
        return {"answer": answer, "backend": backend, "tier": "standard", "repaired": False}

    # Repair: 调强模型修复
    repaired = _repair(query, answer, gate["reasons"], msgs, call_fn, system, max_tokens)
    if repaired:
        return {"answer": repaired[1], "backend": repaired[0], "tier": "standard", "repaired": True}

    # 修复失败，返回原始答案（总比没有好）
    return {"answer": answer, "backend": backend, "tier": "standard", "repaired": False}


def _execute_complex(query: str, messages: list, call_fn,
                     system: str, max_tokens: int) -> dict:
    """Complex 层：Strong 规划 + Coder 执行 + Strong 审查。"""
    msgs = [{"role": "user", "content": query}]
    if len(messages) > 1:
        msgs = messages[:-1] + [{"role": "user", "content": query}]

    # 复杂任务直接用 Strong 模型（质量优先）
    backend, answer = _try_backends("strong", msgs, call_fn, system, max_tokens)
    if answer:
        gate = quality_gate.check(answer, query)
        if gate["passed"]:
            return {"answer": answer, "backend": backend, "tier": "complex", "repaired": False}

    # Strong 失败或质量不达标，降级到 Coder
    backend, answer = _try_backends("coder", msgs, call_fn, system, max_tokens)
    return {"answer": answer or "", "backend": backend or "exhausted",
            "tier": "complex", "repaired": False}


def _repair(query: str, bad_answer: str, reasons: list,
            messages: list, call_fn, system: str, max_tokens: int) -> tuple:
    """调强模型修复低质量回复。返回 (backend, answer) 或 None。"""
    repair_prompt = (
        f"以下代码回复存在问题: {', '.join(reasons)}\n\n"
        f"原始问题: {query}\n\n"
        f"有问题的回复:\n{bad_answer[:2000]}\n\n"
        f"请修复上述问题，直接给出正确的完整回复。"
    )
    repair_msgs = messages[:-1] + [{"role": "user", "content": repair_prompt}]
    backend, answer = _try_backends("strong", repair_msgs, call_fn, system, max_tokens)
    if answer and len(answer.strip()) > 10:
        return backend, answer
    return None
