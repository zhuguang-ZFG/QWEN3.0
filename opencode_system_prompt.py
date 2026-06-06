"""opencode_system_prompt.py — 系统提示按模型族路由。

复刻 OpenCode session/system.ts 的 SystemPrompt.provider() (L19-33)。

OpenCode 按模型族选择不同的系统提示模板:
- GPT-4/o1/o3: "beast" 模板 (最强能力)
- GPT (其他): "gpt" 模板 (codex 除外用 "codex")
- Gemini: "gemini" 模板
- Claude: "anthropic" 模板
- Trinity: "trinity" 模板
- Kimi: "kimi" 模板
- 默认: "default" 模板

LiMa 服务端根据模型族注入针对性的系统提示优化指令，
提升不同模型的编码能力表现。

源码参考:
  - opencode-source/packages/opencode/src/session/system.ts (L19-33)
"""

from __future__ import annotations

import logging
import re

_log = logging.getLogger(__name__)


# ── 模型族检测模式 (system.ts:19-33) ──────────────────────────────────────
_BEAST_PATTERN = re.compile(
    r"(gpt-?4|o1|o3|o4|gpt-?5)",
    re.IGNORECASE,
)
_CODEX_PATTERN = re.compile(r"codex", re.IGNORECASE)
_GPT_PATTERN = re.compile(r"gpt", re.IGNORECASE)
_GEMINI_PATTERN = re.compile(r"gemini", re.IGNORECASE)
_ANTHROPIC_PATTERN = re.compile(r"(claude|anthropic)", re.IGNORECASE)
_TRINITY_PATTERN = re.compile(r"trinity", re.IGNORECASE)
_KIMI_PATTERN = re.compile(r"(kimi|moonshot)", re.IGNORECASE)
_DEEPSEEK_PATTERN = re.compile(r"deepseek|(?:^|[_\-])ds(?:[_\-]|$)", re.IGNORECASE)
_QWEN_PATTERN = re.compile(r"qwen", re.IGNORECASE)
_LLAMA_PATTERN = re.compile(r"llama", re.IGNORECASE)


def resolve_prompt_template(model: str, backend_name: str = "") -> str:
    """根据模型族选择系统提示模板名。

    复刻 SystemPrompt.provider() (system.ts:19-33)。

    Args:
        model: 模型标识符 (如 "gpt-4o", "claude-sonnet-4-20250514")。
        backend_name: 后端名称 (辅助判断)。

    Returns:
        模板名称: "beast" | "gpt" | "codex" | "gemini" | "anthropic" |
                  "trinity" | "kimi" | "deepseek" | "qwen" | "llama" | "default"
    """
    combined = f"{model} {backend_name}"

    # 高优先级: 特定模型族
    if _BEAST_PATTERN.search(model):
        return "beast"
    if _CODEX_PATTERN.search(combined):
        return "codex"
    if _GEMINI_PATTERN.search(combined):
        return "gemini"
    if _ANTHROPIC_PATTERN.search(combined):
        return "anthropic"
    if _TRINITY_PATTERN.search(combined):
        return "trinity"
    if _KIMI_PATTERN.search(combined):
        return "kimi"

    # 中等优先级: LiMa 扩展的模型族
    if _DEEPSEEK_PATTERN.search(combined):
        return "deepseek"
    if _QWEN_PATTERN.search(combined):
        return "qwen"
    if _LLAMA_PATTERN.search(combined):
        return "llama"

    # GPT 系列 (非 beast/codex)
    if _GPT_PATTERN.search(combined):
        return "gpt"

    return "default"


# ── 模型族优化指令 (LiMa 扩展) ────────────────────────────────────────────

_TEMPLATE_HINTS: dict[str, str] = {
    "beast": (
        "You are using a high-capability model. "
        "Leverage extended reasoning for complex tasks. "
        "Provide thorough, precise code with minimal explanation."
    ),
    "gpt": (
        "Focus on producing clean, working code. "
        "Use function/tool calls when available. "
        "Be concise and action-oriented."
    ),
    "codex": (
        "You are in a code-focused environment. "
        "Produce complete, executable code without shortcuts."
    ),
    "gemini": (
        "You have strong multimodal capabilities. "
        "Leverage long context for large codebase understanding. "
        "Be precise with tool parameters."
    ),
    "anthropic": (
        "Use extended thinking for complex problems. "
        "Prefer structured outputs. "
        "Be thorough in code review and generation."
    ),
    "trinity": (
        "Focus on balanced performance and accuracy."
    ),
    "kimi": (
        "Optimize for long context utilization. "
        "Be precise with Chinese and English code comments."
    ),
    "deepseek": (
        "Focus on code generation quality. "
        "Leverage strong code completion capabilities. "
        "Provide complete implementations."
    ),
    "qwen": (
        "Focus on multilingual code generation. "
        "Be thorough with tool use and structured output."
    ),
    "llama": (
        "Keep responses focused and concise. "
        "Prioritize working code over explanations."
    ),
    "default": "",
}


def get_model_family_hint(model: str, backend_name: str = "") -> str:
    """获取模型族的系统提示优化指令。

    Args:
        model: 模型标识符。
        backend_name: 后端名称。

    Returns:
        优化指令字符串 (空字符串表示不需要额外指令)。
    """
    template = resolve_prompt_template(model, backend_name)
    return _TEMPLATE_HINTS.get(template, "")


def enhance_system_prompt(
    system_prompt: str,
    model: str,
    backend_name: str = "",
    environment_info: dict[str, str] | None = None,
) -> str:
    """增强系统提示，注入模型族优化指令和环境信息。

    复刻 system.ts 的完整流程:
    1. 选择模型族模板
    2. 注入环境信息 (OS, cwd, shell)
    3. 拼接优化指令

    Args:
        system_prompt: 原始系统提示。
        model: 模型标识符。
        backend_name: 后端名称。
        environment_info: 环境信息 {"os": "...", "cwd": "...", "shell": "..."}。

    Returns:
        增强后的系统提示。
    """
    parts: list[str] = []

    if system_prompt:
        parts.append(system_prompt.rstrip())

    # 模型族优化指令
    hint = get_model_family_hint(model, backend_name)
    if hint:
        parts.append(f"\n## Model Optimization\n{hint}")

    # 环境信息注入 (system.ts:35-50)
    if environment_info:
        env_lines = []
        if environment_info.get("os"):
            env_lines.append(f"- OS: {environment_info['os']}")
        if environment_info.get("cwd"):
            env_lines.append(f"- Working directory: {environment_info['cwd']}")
        if environment_info.get("shell"):
            env_lines.append(f"- Shell: {environment_info['shell']}")
        if env_lines:
            parts.append("\n## Environment\n" + "\n".join(env_lines))

    return "\n".join(parts) if parts else system_prompt


def resolve_provider_kind(model: str, backend_name: str = "") -> str:
    """解析模型所属的 provider 族。

    与 resolve_prompt_template 类似但返回更粗粒度的分类，
    用于其他模块 (如 schema sanitize, prompt cache) 的 provider 判断。

    Args:
        model: 模型标识符。
        backend_name: 后端名称。

    Returns:
        "openai" | "anthropic" | "google" | "kimi" | "deepseek" | "unknown"
    """
    combined = f"{model} {backend_name}"

    if _ANTHROPIC_PATTERN.search(combined):
        return "anthropic"
    if _GEMINI_PATTERN.search(combined):
        return "google"
    if _KIMI_PATTERN.search(combined):
        return "kimi"
    if _DEEPSEEK_PATTERN.search(combined):
        return "deepseek"
    if _GPT_PATTERN.search(combined) or _BEAST_PATTERN.search(model):
        return "openai"

    return "unknown"
