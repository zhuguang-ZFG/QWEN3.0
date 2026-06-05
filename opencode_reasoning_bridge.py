"""opencode_reasoning_bridge.py — 推理内容透传与模型适配。

对齐 OpenCode 的 system.ts 和 openai-chat.ts 的 reasoning_content 处理逻辑。
让弱后端也能受益于推理增强，同时确保不同后端的推理内容格式兼容。

核心功能:
  1. passthrough_reasoning_content() — 确保 reasoning_content 不被过滤
  2. select_provider_system_prompt() — 匹配 OpenCode 的 provider 特定 prompt
  3. adapt_reasoning_for_weak_backend() — 思维链蒸馏
  4. inject_thinking_reminder() — 不支持原生 reasoning 的后端注入思考提示
  5. strip_reasoning_for_non_supporting() — 剥离不兼容的 reasoning 字段

源码参考:
  - opencode-source/packages/opencode/src/session/system.ts (provider prompt selection)
  - opencode-source/packages/llm/src/protocols/openai-chat.ts (reasoning_content in delta/event)
  - opencode-source/packages/opencode/src/session/message-v2.ts (signed reasoning blocks)
"""

from __future__ import annotations

import logging
from typing import Any

_log = logging.getLogger(__name__)

# ── 后端分类：哪些后端支持原生 reasoning_content ─────────────────────────
# 这些后端会在 SSE delta 中返回 reasoning_content 字段

_REASONING_CAPABLE_BACKENDS: set[str] = {
    # DeepSeek 系列（通过 reasoning_content 返回思维链）
    "scnet_ds_flash", "scnet_ds_pro",
    "scnet_large_ds_flash", "scnet_large_ds_pro",
    "nvidia_deepseek_v4",
    "cf_deepseek_r1", "cfai_deepseek_r1",
    "github_deepseek_r1",
    "sambanova_ds_v3",
    # Kimi K2（支持 reasoning）
    "kimi", "cf_kimi_k26",
    # OpenAI o1/o3（原生 reasoning）
    "github_o1", "github_o3",
    # Qwen3 thinking variants
    "or_qwen3_coder",
}

# 明确不支持 reasoning_content 的后端（可能报错如果传递）
_REASONING_INCOMPATIBLE_BACKENDS: set[str] = {
    "groq_gptoss", "groq_gptoss_20b", "groq_llama70b",
    "groq_qwen32b", "groq_llama4",
    "cerebras_gptoss",
    "mistral_small",
    "google_flash_lite", "google_flash",
    "github_gpt4o_mini",
    "cfai_llama4",
}


def supports_reasoning(backend: str) -> bool:
    """判断后端是否支持原生 reasoning_content。"""
    if backend in _REASONING_CAPABLE_BACKENDS:
        return True
    if backend in _REASONING_INCOMPATIBLE_BACKENDS:
        return False
    # Unknown: assume compatible (most OpenAI-compatible APIs ignore unknown fields)
    return True


def is_reasoning_incompatible(backend: str) -> bool:
    """判断后端是否明确不兼容 reasoning_content。"""
    return backend in _REASONING_INCOMPATIBLE_BACKENDS


# ── reasoning_content 透传 ────────────────────────────────────────────────

def passthrough_reasoning_content(
    chunk: dict,
    backend: str = "",
) -> dict:
    """确保 reasoning_content 在 SSE chunk 透传中不被过滤。

    OpenCode 的 openai-chat.ts 期望:
      - delta.reasoning_content: string|null (流式推理 token)
      - 在 finish_reason 到达前持续接收 reasoning delta

    本函数确保：
      - reasoning_content 字段存在于 delta 中（如果后端返回了）
      - 不做任何截断或过滤

    Args:
        chunk: SSE chunk dict。
        backend: 后端名称。

    Returns:
        透传处理后的 chunk。
    """
    # No-op: LiMa 的流式代理默认透传所有字段
    # 此函数作为显式标记点，确保未来修改不会意外过滤 reasoning_content
    choices = chunk.get("choices") or []

    for choice in choices:
        if not isinstance(choice, dict):
            continue
        delta = choice.get("delta") or {}
        # Ensure reasoning_content is preserved as-is
        if "reasoning_content" in delta:
            _log.debug("Passthrough reasoning_content: %d chars",
                       len(str(delta["reasoning_content"] or "")))

    return chunk


def strip_reasoning_for_non_supporting(
    chunk: dict,
    backend: str = "",
) -> dict:
    """对不兼容 reasoning_content 的后端，剥离该字段避免报错。

    某些后端（Groq fast, Cerebras）可能因未知字段报 400 错误。

    Args:
        chunk: SSE chunk dict。
        backend: 后端名称。

    Returns:
        剥离 reasoning_content 后的 chunk。
    """
    if not is_reasoning_incompatible(backend):
        return chunk

    choices = chunk.get("choices")
    if not choices:
        return chunk

    modified = False
    new_choices = []
    for choice in choices:
        if not isinstance(choice, dict):
            new_choices.append(choice)
            continue
        delta = choice.get("delta") or {}
        if "reasoning_content" in delta:
            # Convert reasoning to a text prefix for weak backends
            reasoning = delta.get("reasoning_content", "")
            content = delta.get("content", "")
            if reasoning and isinstance(reasoning, str) and reasoning.strip():
                # Prepend reasoning as italic text
                thinking_prefix = f"[Thinking: {reasoning.strip()[:200]}]\n\n"
                new_delta = {
                    k: v for k, v in delta.items()
                    if k != "reasoning_content"
                }
                new_delta["content"] = thinking_prefix + (content or "")
                new_choices.append({**choice, "delta": new_delta})
                modified = True
                _log.debug("Stripped reasoning_content → text prefix (%d chars)",
                           len(reasoning))
            else:
                new_delta = {
                    k: v for k, v in delta.items()
                    if k != "reasoning_content"
                }
                new_choices.append({**choice, "delta": new_delta})
                modified = True
        else:
            new_choices.append(choice)

    if modified:
        return {**chunk, "choices": new_choices}
    return chunk


# ── Provider-specific system prompt selection ──────────────────────────────
# 对齐 OpenCode system.ts 的 provider() 函数逻辑

def select_provider_system_prompt(backend: str) -> str:
    """根据后端类型选择匹配 OpenCode 行为的 system prompt 策略。

    OpenCode system.ts 根据 model.api.id 选择：
      - 包含 "gpt-4"/"o1"/"o3" → BEAST prompt
      - 包含 "gpt" + "codex" → CODEX prompt
      - 包含 "gpt" → GPT prompt
      - 包含 "gemini-" → GEMINI prompt
      - 包含 "claude" → ANTHROPIC prompt
      - 包含 "trinity" → TRINITY prompt
      - 包含 "kimi" → KIMI prompt
      - 默认 → DEFAULT prompt

    我们无法获取 OpenCode 的 prompt 原文，但可以注入行为提示：
    - BEAST: 强调最大能力、复杂推理
    - CODEX: 强调代码生成、精确匹配
    - GPT: 强调对话质量
    - GEMINI: 强调长上下文利用
    - ANTHROPIC: 强调安全和逐步推理
    - KIMI: 强调中文优化和长文本

    Args:
        backend: 后端名称。

    Returns:
        要注入的额外 system prompt 提示文本（追加到现有 prompt）。
    """
    lower = backend.lower()

    if any(k in lower for k in ("gpt-4", "o1", "o3", "gptoss_120b")):
        return _BEAST_HINT
    if "codex" in lower:
        return _CODEX_HINT
    if "gpt" in lower:
        return _GPT_HINT
    if "gemini" in lower:
        return _GEMINI_HINT
    if "claude" in lower:
        return _ANTHROPIC_HINT
    if "trinity" in lower:
        return _TRINITY_HINT
    if "kimi" in lower:
        return _KIMI_HINT
    # Qwen Coder → code-focused
    if "coder" in lower:
        return _CODEX_HINT
    # DeepSeek → reasoning-focused
    if "deepseek" in lower or "ds_" in lower:
        return _DEEPSEEK_HINT

    return ""


# ── Provider hint texts (aligned with OpenCode system.ts behavior) ─────────

_BEAST_HINT = (
    "\n## Model Capability Mode: MAXIMUM\n"
    "- You are running on a top-tier model with strong reasoning capabilities.\n"
    "- Take advantage of your full context window for comprehensive analysis.\n"
    "- Provide thorough, well-structured responses with detailed explanations.\n"
    "- Handle complex multi-step tasks with confidence.\n"
)

_CODEX_HINT = (
    "\n## Model Capability Mode: CODE GENERATION\n"
    "- You are optimized for code generation and editing tasks.\n"
    "- Prioritize correct, working code over lengthy explanations.\n"
    "- Follow the user's existing code style and patterns precisely.\n"
    "- Test your code mentally before outputting — ensure it compiles/runs.\n"
    "- Use the most appropriate tool for each code modification.\n"
)

_GPT_HINT = (
    "\n## Model Capability Mode: BALANCED\n"
    "- Balance between code generation and explanation.\n"
    "- Provide clear reasoning alongside code changes.\n"
    "- Use tools appropriately for the task at hand.\n"
)

_GEMINI_HINT = (
    "\n## Model Capability Mode: LONG CONTEXT\n"
    "- You have access to a very large context window.\n"
    "- You can process and analyze large amounts of code in a single pass.\n"
    "- Take advantage of your context for comprehensive file analysis.\n"
    "- Handle multi-file refactoring tasks efficiently.\n"
)

_ANTHROPIC_HINT = (
    "\n## Model Capability Mode: SAFE & THOROUGH\n"
    "- Prioritize safety and correctness in code changes.\n"
    "- Think step by step before making modifications.\n"
    "- Consider edge cases and error handling.\n"
    "- Verify changes by reading files after modification.\n"
)

_TRINITY_HINT = (
    "\n## Model Capability Mode: MULTI-PERSPECTIVE\n"
    "- Consider multiple approaches before committing to one.\n"
    "- Evaluate trade-offs between different solutions.\n"
    "- Provide the most robust solution for the user's context.\n"
)

_KIMI_HINT = (
    "\n## Model Capability Mode: LONG-FORM & CN-OPTIMIZED\n"
    "- Optimized for long-form content and Chinese language tasks.\n"
    "- Handle large files and extensive codebases effectively.\n"
    "- Provide detailed, well-organized responses.\n"
)

_DEEPSEEK_HINT = (
    "\n## Model Capability Mode: DEEP REASONING\n"
    "- You have strong reasoning capabilities — think before acting.\n"
    "- Analyze problems thoroughly before proposing solutions.\n"
    "- Consider multiple angles and edge cases.\n"
    "- Provide well-reasoned, correct code solutions.\n"
)


# ── 弱后端思维链蒸馏 ──────────────────────────────────────────────────────

def adapt_reasoning_for_weak_backend(
    strong_reasoning: str,
    target_backend: str = "",
) -> str:
    """将强模型的推理过程提炼为弱后端的上下文提示。

    从强模型（如 DeepSeek R1）的 reasoning_content 中提取要点，
    作为弱后端的额外上下文注入。

    Args:
        strong_reasoning: 强模型的 reasoning_content 文本。
        target_backend: 目标弱后端名称。

    Returns:
        精简的推理摘要，作为弱后端的上下文提示。
    """
    if not strong_reasoning or not strong_reasoning.strip():
        return ""

    # Extract key sentences (heuristic: first sentence of each logical block)
    lines = strong_reasoning.strip().split("\n")
    key_points: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Skip meta-commentary
        if any(skip in stripped.lower() for skip in (
            "i should", "let me", "i need to", "i will", "okay", "first,",
            "now i", "next,", "then,", "finally,",
        )):
            # Extract the actual insight after the meta phrase
            for marker in ("i should", "let me", "i need to", "i will"):
                idx = stripped.lower().find(marker)
                if idx >= 0:
                    after = stripped[idx + len(marker):].strip().lstrip(":")
                    if after and len(after) > 10:
                        key_points.append(after.strip(" ,."))
                    break
            continue

        if len(stripped) > 15:
            key_points.append(stripped)

    if not key_points:
        return ""

    # Limit to top 5 key points
    distilled = key_points[:5]
    return (
        "\n## Context from prior analysis:\n"
        + "\n".join(f"- {p}" for p in distilled)
    )


# ── 思考提示注入 ──────────────────────────────────────────────────────────

def inject_thinking_reminder(
    messages: list[dict],
    backend: str = "",
) -> list[dict]:
    """对不支持原生 reasoning 的弱后端，注入"请先思考再回答"的提示。

    仿照 DeepSeek R1 的思维链效果，引导弱后端在生成代码前进行内部推理。

    Args:
        messages: 消息列表。
        backend: 后端名称。

    Returns:
        注入后的消息列表。
    """
    if supports_reasoning(backend):
        return list(messages)

    hint = _THINKING_REMINDER_PROMPT

    result = list(messages)
    for i, msg in enumerate(result):
        if msg.get("role") == "system":
            content = msg.get("content", "")
            if isinstance(content, str):
                result[i] = {**msg, "content": content.rstrip() + "\n" + hint}
            elif isinstance(content, list):
                result[i] = {
                    **msg,
                    "content": content + [{"type": "text", "text": hint}],
                }
            return result
    result.insert(0, {"role": "system", "content": hint})
    return result


_THINKING_REMINDER_PROMPT = (
    "\n## Before responding, follow this internal reasoning process:\n"
    "1. **Understand**: What exactly is the user asking for?\n"
    "2. **Plan**: What tools and steps are needed?\n"
    "3. **Verify**: Will the proposed solution actually work?\n"
    "4. **Execute**: Provide the solution concisely.\n"
    "\n"
    "Do NOT output your thinking process — just the result.\n"
    "But DO follow the process internally for better quality.\n"
)


# ── SSE delta reasoning 处理 ──────────────────────────────────────────────

def process_reasoning_delta(
    chunk: dict,
    backend: str = "",
) -> dict:
    """处理 SSE delta 中的 reasoning_content。

    综合处理：
      1. 对兼容后端：透传 reasoning_content
      2. 对不兼容后端：剥离并转为文本前缀
      3. 对弱后端无 reasoning：不需要处理

    Args:
        chunk: SSE chunk dict。
        backend: 后端名称。

    Returns:
        处理后的 chunk。
    """
    # Always passthrough first
    chunk = passthrough_reasoning_content(chunk, backend)

    # Strip for incompatible backends
    if is_reasoning_incompatible(backend):
        chunk = strip_reasoning_for_non_supporting(chunk, backend)

    return chunk


# ── 累积 reasoning 状态跟踪 ────────────────────────────────────────────────

def track_reasoning_state(
    accumulated_reasoning: str,
    chunk: dict,
) -> str:
    """跟踪累积的 reasoning_content，用于后续蒸馏。

    在流式场景中逐步累积 reasoning 文本，finish 后可用于 distill 到弱后端。

    Args:
        accumulated_reasoning: 之前累积的 reasoning 文本。
        chunk: 当前 SSE chunk。

    Returns:
        更新后的累积 reasoning 文本。
    """
    choices = chunk.get("choices") or []
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        delta = choice.get("delta") or {}
        rc = delta.get("reasoning_content", "")
        if rc and isinstance(rc, str):
            accumulated_reasoning += rc
    return accumulated_reasoning


# ── 综合处理入口 ───────────────────────────────────────────────────────────

def apply_reasoning_bridge(
    messages: list[dict],
    backend: str = "",
    system_prompt: str = "",
    chunk: dict | None = None,
    accumulated_reasoning: str = "",
) -> tuple[list[dict], dict | None, str]:
    """综合应用 reasoning bridge 的全部功能。

    在 routing_engine 中调用此函数处理：
      1. SSE chunk 级别的 reasoning_content 透传/剥离
      2. Message 级别的 thinking reminder 注入
      3. Provider 特定的 system prompt 选择

    Args:
        messages: 消息列表。
        backend: 当前后端。
        system_prompt: 现有 system prompt。
        chunk: 当前 SSE chunk（流式场景）。
        accumulated_reasoning: 累积的 reasoning 文本。

    Returns:
        (updated_messages, updated_chunk, updated_accumulated_reasoning)
    """
    # 1. Process SSE chunk
    updated_chunk = chunk
    updated_reasoning = accumulated_reasoning
    if chunk:
        updated_chunk = process_reasoning_delta(chunk, backend)
        updated_reasoning = track_reasoning_state(accumulated_reasoning, chunk)

    # 2. Inject thinking reminder for weak backends
    updated_messages = inject_thinking_reminder(messages, backend)

    # 3. Inject provider-specific system prompt
    provider_hint = select_provider_system_prompt(backend)
    if provider_hint:
        updated_messages = _append_to_system(updated_messages, provider_hint)

    return updated_messages, updated_chunk, updated_reasoning


def _append_to_system(messages: list[dict], text: str) -> list[dict]:
    """追加文本到 system message。"""
    result = list(messages)
    for i, msg in enumerate(result):
        if msg.get("role") == "system":
            content = msg.get("content", "")
            if isinstance(content, str):
                result[i] = {**msg, "content": content.rstrip() + "\n" + text}
            elif isinstance(content, list):
                result[i] = {
                    **msg,
                    "content": content + [{"type": "text", "text": text}],
                }
            return result
    result.insert(0, {"role": "system", "content": text})
    return result
