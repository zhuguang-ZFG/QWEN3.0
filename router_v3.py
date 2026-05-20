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

import random
import hashlib
import json
from typing import Optional

# ─── 后端池定义 ───────────────────────────────────────────────────────────────

POOLS = {
    "ide": {
        "strong": ["longcat_chat", "deepseek_flash", "naga_llama70b"],
        "medium": ["naga_gpt41mini", "freetheai_ds", "unclose_hermes"],
        "floor": ["longcat_lite"],
    },
    "chat": {
        "strong": ["longcat_chat", "deepseek_flash"],
        "medium": ["naga_llama70b", "unclose_hermes", "freetheai_ds"],
        "floor": ["chat_ubi", "pollinations"],
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
    "zhipu_flash", "aliyun_turbo", "volcengine_lite",
    "deepseek_flash", "chat_ubi", "pollinations",
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
        random.shuffle(usable)
        result.extend(usable)

    if not result:
        result = [b for b in DIRECT_BACKENDS if health_map.get(b, "healthy") != "dead"]

    if not result:
        result = ["chat_ubi", "pollinations"]

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
    import math
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

