"""
LiMa Router V3 — 三层路由架构
Layer 1: 请求分类器 (classify_request)
Layer 2: 后端池选择 (select_backends)
Layer 3: 执行器 (execute)

设计原则:
- IDE 请求永远不走弱后端
- 后端选择基于实时健康状态
- 同层随机消除死模型
- 全部失败返回诚实错误，不降级到不可接受质量
"""

import math
import random
import hashlib
import json
from typing import Optional

# ─── 后端池定义 ───────────────────────────────────────────────────────────────

# NOTE: groq/cerebras keys expired 2026-05-20, moved to medium until renewed
POOLS = {
    "ide": {
        "strong": ["zhipu_flash", "longcat_chat", "deepseek_free", "mistral_large",
                   "opencode_stealth", "fireworks_llama405b"],
        "medium": ["groq_llama70b", "cerebras_gptoss", "groq_qwen32b", "groq_gptoss_20b",
                   "cerebras_qwen235b", "mistral_devstral", "aliyun_qwen3", "nvidia_qwen_coder",
                   "opencode_ds_flash", "opencode_qwen", "opencode_nemotron", "opencode_minimax",
                   "sambanova_llama4", "cohere_command",
                   "deepinfra_llama4", "deepinfra_qwen235b"],
        "floor": ["longcat_lite", "google_flash", "ovh_llama70b", "ovh_deepseek"],
    },
    "chat": {
        "strong": ["zhipu_flash", "longcat_chat", "deepseek_free",
                   "opencode_stealth", "fireworks_llama405b"],
        "medium": ["groq_llama70b", "cerebras_gptoss", "groq_qwen32b", "mistral_large",
                   "nvidia_qwen_coder", "sambanova_llama4", "cohere_command",
                   "deepinfra_llama4", "deepinfra_qwen235b"],
        "floor": ["longcat_lite", "google_flash", "ovh_llama70b", "ovh_deepseek"],
    },
    "vision": {
        "strong": ["longcat_omni"],
        "floor": ["pollinations"],
    },
    "image": {
        "strong": ["pollinations"],
    },
}

DIRECT_BACKENDS = [
    "zhipu_flash", "zhipu_flash7", "aliyun_turbo", "volcengine_lite",
    "deepseek_flash", "silicon_qwen8b", "chat_ubi", "llm7", "pollinations",
    "deepseek_free", "local_qwen_coder",
]

IDE_SOURCES = {"Claude Code", "claude_code", "Cursor", "cursor",
               "Codex", "codex", "Aider", "aider", "Cline", "cline"}

_IDE_FINGERPRINTS = {
    "cursor": ["intelligent programmer", "You are Cursor"],
    "claude_code": ["CLAUDE.md", "Claude Code", "EnterPlanMode"],
    "codex": ["Codex", "codex"],
    "aider": ["SEARCH/REPLACE", "RepoMap"],
    "cline": ["<environment_details>", "Cline"],
    "continue": ["Continue is an open-source", "continue.dev"],
}

MAX_FALLBACKS = 5


# ─── Layer 1: 请求分类器 ─────────────────────────────────────────────────────

def classify_request(path: str, headers: dict, body: dict) -> dict:
    """看元数据分类，不看内容。<1ms"""
    req_type = "chat"

    if path.startswith("/v1/messages"):
        req_type = "ide"
    else:
        ua = headers.get("user-agent", "").lower()
        if any(x in ua for x in ["claude-code", "cursor", "aider", "codex"]):
            req_type = "ide"

    if req_type != "ide":
        system = _extract_system(body)
        if system:
            for ide, markers in _IDE_FINGERPRINTS.items():
                if any(m in system for m in markers):
                    req_type = "ide"
                    break

    if req_type != "ide":
        if _has_image_blocks(body):
            req_type = "vision"

    return {"type": req_type}


def _extract_system(body: dict) -> str:
    system = body.get("system", "")
    if isinstance(system, list):
        return " ".join(b.get("text", "") for b in system if b.get("type") == "text")
    if isinstance(system, str) and system:
        return system
    msgs = body.get("messages", [])
    for m in msgs:
        if isinstance(m, dict) and m.get("role") == "system":
            c = m.get("content", "")
            return c if isinstance(c, str) else ""
    return ""


def _has_image_blocks(body: dict) -> bool:
    for m in body.get("messages", []):
        content = m.get("content", "") if isinstance(m, dict) else ""
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") in ("image", "image_url"):
                    return True
    return False


# ─── Layer 2: 后端池选择 ─────────────────────────────────────────────────────

def select_backends(req_type: str, health_map: dict, proxy_healthy: bool = True) -> list:
    """从对应 Pool 选健康后端，同层随机，P2C 优化"""
    pool = POOLS.get(req_type, POOLS["chat"])
    result = []

    for tier in ("strong", "medium", "floor"):
        candidates = pool.get(tier, [])
        if not proxy_healthy:
            candidates = [b for b in candidates if b in DIRECT_BACKENDS]
        usable = [b for b in candidates if health_map.get(b, "healthy") != "dead"]
        # Keep declared order as priority (no shuffle)
        result.extend(usable)

    if not result:
        result = [b for b in DIRECT_BACKENDS if health_map.get(b, "healthy") != "dead"]

    # 极端保底：只加非 dead 的
    if not result:
        result = [b for b in ["chat_ubi", "pollinations"]
                  if health_map.get(b, "healthy") != "dead"]

    return result[:MAX_FALLBACKS]


def p2c_select(backends: list, score_fn) -> Optional[str]:
    """Power of Two Choices: 随机选2个，取更健康的"""
    if not backends:
        return None
    if len(backends) == 1:
        return backends[0]
    i, j = random.sample(range(len(backends)), 2)
    si, sj = score_fn(backends[i]), score_fn(backends[j])
    return backends[i] if si >= sj else backends[j]


# ─── Layer 3: 执行辅助 ───────────────────────────────────────────────────────

def detect_mass_failure(health_map: dict) -> bool:
    """超过 50% 后端 dead = 我们自己的问题（代理/网络）"""
    if not health_map:
        return False
    dead = sum(1 for s in health_map.values() if s == "dead")
    return dead > len(health_map) * 0.5


def compute_health_score(backend: str, health_map: dict, latency_map: dict) -> float:
    """P2C 健康分: 成功率 + 延迟倒数 - 熔断惩罚"""
    state = health_map.get(backend, "healthy")
    if state == "dead":
        return -1.0
    latency = latency_map.get(backend, 1000)
    score = 1.0 / math.log10(latency + 10)
    if state == "degraded":
        score *= 0.5
    return score


def semantic_cache_key(model: str, messages: list, temperature: float = 0) -> str:
    """精确匹配缓存 key (仅 temperature=0 时有效)"""
    if temperature != 0:
        return ""
    payload = json.dumps({"model": model, "messages": messages}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


# ─── Skills 注入判断 ─────────────────────────────────────────────────────────

STRONG_BACKENDS = {"longcat_chat", "deepseek_flash", "deepseek_pro", "naga_gpt41mini",
                  "opencode_stealth", "fireworks_llama405b", "deepinfra_llama4", "deepseek_free"}

_LANG_KEYWORDS = {
    "python": ["python", "pip", "django", "flask", "fastapi", "pep"],
    "javascript": ["javascript", "typescript", "react", "vue", "node", "npm"],
    "go": ["golang", " go ", "goroutine", "go mod"],
    "rust": ["rust", "cargo", "borrow"],
    "java": ["java", "spring", "maven", "gradle"],
}


def detect_ide_from_system_prompt(text: str) -> str:
    """公开接口：从 system prompt 检测 IDE 来源"""
    for ide, markers in _IDE_FINGERPRINTS.items():
        if any(m in text for m in markers):
            return ide
    return ""


def get_skills_to_inject(ide_source: str, system_prompt: str,
                         backend: str, detected_lang: str = "") -> dict:
    """
    智能判断需要注入哪些 Skills 层级。
    返回 {"L0": bool, "L1": bool, "L2": bool, "L3": bool}
    """
    result = {"L0": False, "L1": False, "L2": False, "L3": False}
    is_ide = ide_source in IDE_SOURCES
    is_strong = backend in STRONG_BACKENDS
    sys_lower = system_prompt.lower()

    # L0: 通用编程规范 — 只有无 system prompt 的普通聊天才注入
    if not is_ide and len(system_prompt) < 100:
        result["L0"] = True

    # L1: 语言专属规则 — 检测 system prompt 是否已覆盖该语言
    if detected_lang:
        keywords = _LANG_KEYWORDS.get(detected_lang, [])
        already_covered = any(kw in sys_lower for kw in keywords)
        if not already_covered:
            result["L1"] = True

    # L2: 项目专属上下文 — 永远注入（IDE 不知道我们的项目约定）
    result["L2"] = True

    # L3: 模型专属提示 — 弱模型才注入
    if not is_strong:
        result["L3"] = True

    return result

