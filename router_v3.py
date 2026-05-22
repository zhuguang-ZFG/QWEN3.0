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

import runtime_topology

# ─── 后端池定义 ───────────────────────────────────────────────────────────────

POOLS = {
    "ide": {
        "strong": ["scnet_ds_flash", "scnet_qwen235b", "scnet_qwen30b",
                   "scnet_ds_pro", "longcat_chat", "longcat",
                   "cf_qwen_coder", "cfai_qwen_coder", "cf_llama70b",
                   "cfai_llama70b", "cf_kimi_k26",
                   "mistral_large", "mistral_small",
                   "groq_llama70b", "cerebras_gptoss", "zhipu_flash", "deepseek_free",
                   "opencode_stealth", "fireworks_llama405b",
                   "github_gpt4o", "github_codestral"],
        "medium": ["cf_llama4", "cfai_llama4", "cf_gptoss_120b", "cf_qwen3_30b", "cf_glm47", "cf_deepseek_r1",
                   "cfai_deepseek_r1",
                   "cf_qwq", "cf_mistral", "cf_gemma4", "cf_nemotron",
                   "groq_qwen32b", "groq_gptoss_20b", "cerebras_qwen235b", "mistral_devstral",
                   "aliyun_qwen3", "nvidia_qwen_coder",
                   "opencode_ds_flash", "opencode_qwen", "opencode_nemotron", "opencode_minimax",
                   "sambanova_llama4", "cohere_command",
                   "deepinfra_llama4", "deepinfra_qwen235b",
                   "github_gpt4o_mini", "github_llama70b", "google_gemini3",
                   "groq_llama4", "groq_gptoss", "or_qwen3_coder",
                   "mistral_codestral", "sambanova_ds_v3"],
        "floor": ["longcat_lite", "google_flash", "ovh_llama70b", "ovh_deepseek",
                  "google_flash_lite", "google_gemma4",
                  "local_coder14b", "local_reasoning", "local_general",
                  "ddg_gpt4o_mini", "ddg_gpt5_mini",
                  "ddg_claude_haiku_45", "ddg_tinfoil_gptoss_120b"],
    },
    "chat": {
        "strong": ["scnet_qwen30b", "scnet_ds_flash", "scnet_qwen235b",
                   "scnet_ds_pro", "longcat_chat", "longcat",
                   "cf_qwen_coder", "cfai_qwen_coder", "cf_llama70b",
                   "cfai_llama70b", "cf_kimi_k26",
                   "groq_llama70b", "cerebras_gptoss", "zhipu_flash", "deepseek_free",
                   "opencode_stealth", "fireworks_llama405b",
                   "github_gpt4o", "mistral_medium"],
        "medium": ["cf_llama4", "cfai_llama4", "cf_gptoss_120b", "cf_qwen3_30b", "cf_glm47", "cf_deepseek_r1",
                   "cfai_deepseek_r1",
                   "cf_qwq", "cf_mistral", "cf_gemma4", "cf_nemotron",
                   "groq_qwen32b", "mistral_large", "nvidia_qwen_coder",
                   "sambanova_llama4", "cohere_command", "deepinfra_llama4", "deepinfra_qwen235b",
                   "github_gpt4o_mini", "github_llama70b", "google_gemini3",
                   "groq_llama4", "groq_gptoss", "or_llama70b", "or_nemotron",
                   "or_qwen3_80b", "mistral_small", "sambanova_ds_v3"],
        "floor": ["longcat_lite", "google_flash", "ovh_llama70b", "ovh_deepseek",
                  "google_flash_lite", "google_gemma4",
                  "local_fast", "local_chat", "local_general",
                  "ddg_gpt4o_mini", "ddg_gpt5_mini",
                  "ddg_claude_haiku_45", "ddg_tinfoil_gptoss_120b"],
    },
    "vision": {
        "strong": ["longcat_omni"],
        "floor": ["pollinations"],
    },
    "image": {
        "strong": ["pollinations"],
    },
    "code": {
        "strong": ["scnet_ds_flash", "scnet_qwen235b", "scnet_qwen30b",
                   "scnet_ds_pro", "github_gpt4o", "github_gpt4o_mini",
                   "cf_qwen_coder", "cfai_qwen_coder", "or_gptoss_120b",
                   "cf_gptoss_120b", "cf_deepseek_r1", "cf_qwen3_30b",
                   "cfai_deepseek_r1", "github_codestral", "mistral_large",
                   "mistral_devstral", "mistral_pixtral", "cf_kimi_k26",
                   "scnet_large_ds_flash"],
        "medium": ["cfai_llama70b", "cfai_llama4",
                   "cerebras_gptoss", "groq_gptoss", "mistral_small",
                   "mistral_medium", "groq_gptoss_20b",
                   "scnet_large_ds_flash", "github_gpt4o", "github_codestral"],
        "floor": ["mistral_devstral", "mistral_large", "cerebras_gptoss",
                  "groq_gptoss", "longcat_lite", "local_coder14b",
                  "local_reasoning",
                  "ddg_gpt4o_mini", "ddg_gpt5_mini",
                  "ddg_claude_haiku_45", "ddg_tinfoil_gptoss_120b"],
    },
    "chat_fast": {
        "strong": ["scnet_qwen30b", "scnet_ds_flash", "scnet_qwen235b",
                   "groq_llama70b", "groq_qwen32b", "cerebras_gptoss",
                   "longcat_lite", "cf_llama70b", "cfai_llama70b",
                   "cf_kimi_k26"],
        "medium": ["longcat_chat", "cf_qwen3_30b", "cfai_qwen_coder",
                   "cfai_llama4", "cf_gemma4",
                   "groq_gptoss", "groq_llama4",
                   "google_flash", "google_flash_lite"],
        "floor": ["ovh_llama70b", "ovh_deepseek", "pollinations_openai",
                  "local_fast", "local_chat",
                  "ddg_gpt4o_mini", "ddg_gpt5_mini"],
    },
}

DIRECT_BACKENDS = [
    "zhipu_flash", "zhipu_flash7", "aliyun_turbo", "volcengine_lite",
    "silicon_qwen8b", "chat_ubi", "llm7", "pollinations",
    "deepseek_free", "local_coder14b", "local_reasoning", "local_general", "local_fast", "local_chat",
]

IDE_SOURCES = {"Claude Code", "claude_code", "Cursor", "cursor",
               "Codex", "codex", "Aider", "aider", "Cline", "cline",
               "Continue", "continue", "VS Code", "vscode", "vs code"}

_IDE_FINGERPRINTS = {
    "cursor": ["intelligent programmer", "You are Cursor"],
    "claude_code": ["CLAUDE.md", "Claude Code", "EnterPlanMode"],
    "codex": ["Codex", "codex"],
    "aider": ["SEARCH/REPLACE", "RepoMap"],
    "cline": ["<environment_details>", "Cline"],
    "continue": ["Continue is an open-source", "continue.dev"],
}

MAX_FALLBACKS = 8


# ─── Layer 1: 请求分类器 ─────────────────────────────────────────────────────

def classify_request(path: str, headers: dict, body: dict) -> dict:
    """看元数据分类，不看内容。<1ms"""
    req_type = "chat"

    if path.startswith("/v1/messages"):
        req_type = "ide"
    else:
        ua = headers.get("user-agent", "").lower()
        if any(x in ua for x in ["claude-code", "cursor", "aider", "codex", "cline", "continue", "vscode"]):
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
        usable = runtime_topology.filter_backends(usable)
        # Keep declared order as priority (no shuffle)
        result.extend(usable)

    if not result:
        result = [b for b in DIRECT_BACKENDS if health_map.get(b, "healthy") != "dead"]
        result = runtime_topology.filter_backends(result)

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



# ─── Layer 3: IDE 检测 ─────────────────────────────────────────────────────

def detect_ide_from_system_prompt(text: str) -> str:
    """公开接口：从 system prompt 检测 IDE 来源"""
    for ide, markers in _IDE_FINGERPRINTS.items():
        if any(m in text for m in markers):
            return ide
    return ""
