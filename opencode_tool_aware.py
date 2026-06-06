"""opencode_tool_aware.py — OpenCode 工具感知提示注入。

让弱后端知道自己是 OpenCode 的助手，从而在编码场景下表现更好。

核心功能:
  1. 检测 OpenCode 请求特征（system prompt / tool definitions）
  2. 自动注入工具列表摘要到 system prompt
  3. 注入 OpenCode 编码规范（从 opencode-source 源码分析提取）
  4. 对弱后端追加 "think step by step before coding" 约束
  5. 对编码专用后端提供更丰富的上下文

集成点: skills_injector.py → routing_engine.py inject_skills()
"""

from __future__ import annotations

import logging

_log = logging.getLogger(__name__)

# ── OpenCode 工具特征 ─────────────────────────────────────────────────────
# 从 opencode-source/packages/opencode/src/tool/registry.ts 提取
_OPENCODE_TOOL_SIGNATURES: set[str] = {
    "read", "write", "edit", "apply_patch", "glob", "grep",
    "shell", "bash", "task", "todo_write", "web_fetch", "web_search",
    "question", "skill", "lsp", "plan_enter", "plan_exit",
}

# OpenCode system prompt 特征关键词
_OPENCODE_SYSTEM_SIGNATURES = [
    "You are OpenCode",
    "opencode",
    "You are powered by",
    "Working directory:",
    "Workspace root folder:",
]

# ── 后端分类 ──────────────────────────────────────────────────────────────

# 编码专精后端（更适合处理代码生成/修复）
_CODE_SPECIALIZED_BACKENDS: set[str] = {
    "cf_qwen_coder", "cfai_qwen_coder", "nvidia_qwen_coder",
    "nvidia_qwen35_coder", "nvidia_deepseek_v4",
    "mistral_codestral", "mistral_devstral",
    "github_codestral", "or_qwen3_coder",
    "scnet_ds_pro", "scnet_ds_flash",
}

# 弱推理后端（需要 think step by step 提示）
_WEAK_REASONING_BACKENDS: set[str] = {
    "groq_gptoss", "groq_gptoss_20b", "groq_llama70b",
    "groq_qwen32b", "groq_llama4",
    "cerebras_gptoss", "mistral_small",
    "google_flash_lite", "google_flash",
    "cfai_llama70b", "cfai_llama4", "cf_qwen3_30b",
    "github_gpt4o_mini", "deepinfra_llama4",
}

# ── OpenCode 编码规范摘要 ─────────────────────────────────────────────────
# 从 opencode-source 源码的 system prompt 和 tool descriptions 提取

_OPENCODE_CODING_CONVENTIONS = (
    "\n"
    "## OpenCode Coding Standards (MUST follow)\n"
    "- Before editing, ALWAYS read the file first to understand current content.\n"
    "- Use `edit` tool for targeted changes (preferred over `write` for small edits).\n"
    "- Use `write` tool only for creating new files or complete rewrites.\n"
    "- After edits, verify correctness by reading the modified file.\n"
    "- Use `grep` to search for patterns across the codebase before making changes.\n"
    "- Use `glob` to find files by pattern before reading.\n"
    "- Never guess file paths — always verify with `glob` or `read` first.\n"
    "- When fixing bugs, first reproduce with `shell` to see the error.\n"
    "- Keep code changes minimal and focused on the requested task.\n"
    "- Preserve existing code style (indentation, naming, patterns).\n"
    "- If the task is ambiguous, use `question` tool to ask for clarification.\n"
)

# ── 弱后端 think step by step 提示 ────────────────────────────────────────

_THINK_STEP_BY_STEP_PROMPT = (
    "\n"
    "## CRITICAL: Before writing any code, think through these steps:\n"
    "1. Understand what the user is asking for (re-read the query).\n"
    "2. Identify which files need to be read or modified.\n"
    "3. Consider edge cases and error handling.\n"
    "4. Write clean, working code — no TODO, no pass, no stubs.\n"
    "5. After writing, mentally verify: does this actually work?\n"
    "\n"
    "Do NOT output your thinking as text — just follow the steps internally\n"
    "and produce the final code. Be concise and direct.\n"
)


def detect_opencode(
    messages: list[dict],
    system_prompt: str = "",
    tools: list[dict] | None = None,
    headers: dict | None = None,
) -> bool:
    """检测当前请求是否来自 OpenCode IDE。

    多维度检测（任一命中即判定为 OpenCode）：
      1. tools 中包含 OpenCode 特征工具名
      2. system prompt 包含 OpenCode 特征关键词
      3. headers.user-agent 包含 "opencode"

    Returns:
        True if the request is from OpenCode.
    """
    # Check tools for OpenCode signatures
    if tools:
        for tool in tools:
            name = tool.get("function", {}).get("name", "") if isinstance(tool, dict) else ""
            if name in _OPENCODE_TOOL_SIGNATURES:
                _log.debug("OpenCode detected via tool: %s", name)
                return True

    # Check system prompt
    sp = system_prompt or ""
    for msg in messages:
        if msg.get("role") == "system":
            sp = sp or msg.get("content", "")
    if isinstance(sp, str):
        sp_lower = sp.lower()
        for sig in _OPENCODE_SYSTEM_SIGNATURES:
            if sig.lower() in sp_lower:
                _log.debug("OpenCode detected via system prompt: %s", sig)
                return True

    # Check user-agent
    if headers:
        ua = headers.get("user-agent", "") or headers.get("User-Agent", "")
        if "opencode" in ua.lower():
            _log.debug("OpenCode detected via user-agent")
            return True

    return False


def classify_backend_strength(backend: str) -> str:
    """分类后端的编码能力等级。

    Returns:
        "code_specialized": 编码专精（Qwen Coder, DeepSeek Coder 等）
        "weak": 弱推理后端（Groq fast, Cerebras, Mistral Small 等）
        "normal": 普通后端
    """
    if backend in _CODE_SPECIALIZED_BACKENDS:
        return "code_specialized"
    if backend in _WEAK_REASONING_BACKENDS:
        return "weak"
    return "normal"


def build_tool_summary(tools: list[dict] | None) -> str:
    """构建工具列表的可读摘要，用于注入到 system prompt。

    将 OpenAI 格式的 tool definitions 转换为简洁的工具清单，
    帮助弱后端理解可用工具（即使它们不完全支持工具调用）。
    """
    if not tools:
        return ""

    lines = ["\n## Available Tools (OpenCode IDE)"]
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        func = tool.get("function", {}) if isinstance(tool, dict) else {}
        name = func.get("name", "") if isinstance(func, dict) else ""
        desc = func.get("description", "") if isinstance(func, dict) else ""

        if not name:
            continue

        # Truncate long descriptions
        short_desc = desc[:120] + ("..." if len(desc) > 120 else "")
        lines.append(f"- **{name}**: {short_desc}")

    if len(lines) <= 1:
        return ""

    lines.append(
        "\nYou are operating inside OpenCode IDE. The user sends tool results "
        "automatically. Focus on providing correct code that works with these tools."
    )
    return "\n".join(lines)


def inject_opencode_prompt(
    messages: list[dict],
    backend: str = "",
    system_prompt: str = "",
    tools: list[dict] | None = None,
    headers: dict | None = None,
) -> list[dict]:
    """注入 OpenCode 感知的系统提示。

    根据后端类型注入不同的提示内容：
      - 所有后端：工具列表摘要 + 编码规范
      - 弱后端：think step by step 约束
      - 编码专精后端：工具使用建议

    Args:
        messages: 当前消息列表
        backend: 选中的后端名称
        system_prompt: 已有的 system prompt
        tools: 工具定义（OpenAI 格式）
        headers: 请求头

    Returns:
        增强后的消息列表
    """
    if not detect_opencode(messages, system_prompt, tools, headers):
        return messages

    strength = classify_backend_strength(backend)
    _log.info(
        "OpenCode tool-aware injection: backend=%s strength=%s tools=%d",
        backend or "unknown", strength, len(tools) if tools else 0,
    )

    # Build injection content
    parts: list[str] = []

    # Tool summary (all backends)
    tool_summary = build_tool_summary(tools)
    if tool_summary:
        parts.append(tool_summary)

    # Coding conventions (all backends)
    parts.append(_OPENCODE_CODING_CONVENTIONS)

    # Think step by step (weak backends only)
    if strength == "weak":
        parts.append(_THINK_STEP_BY_STEP_PROMPT)

    # Code-specialized: extra guidance
    if strength == "code_specialized":
        parts.append(
            "\n## Code Quality Requirements\n"
            "- Write production-quality, well-typed code.\n"
            "- Include proper error handling and edge case coverage.\n"
            "- Use modern language features where appropriate.\n"
            "- Add brief comments for complex logic only.\n"
        )

    injection = "\n".join(parts)

    # Inject into messages
    result = list(messages)

    # Find existing system message to append to, or create one
    system_index = -1
    for i, msg in enumerate(result):
        if msg.get("role") == "system":
            system_index = i
            break

    if system_index >= 0:
        existing = result[system_index].get("content", "")
        if isinstance(existing, str):
            result[system_index] = {
                **result[system_index],
                "content": existing.rstrip() + "\n" + injection,
            }
        elif isinstance(existing, list):
            result[system_index] = {
                **result[system_index],
                "content": existing + [{"type": "text", "text": injection}],
            }
    else:
        result.insert(0, {"role": "system", "content": injection})

    return result


def is_opencode_tool_call_loop(messages: list[dict]) -> bool:
    """检测是否处于 OpenCode 工具调用循环中。

    特征：
      - 最近 N 条消息中交替出现 assistant (含 tool_calls) 和 tool 角色
      - 存在 OpenCode 特征工具名（read_file, write_file, edit 等）

    Returns:
        True if the conversation is in an OpenCode tool call loop.
    """
    if len(messages) < 4:
        return False

    recent = messages[-8:]  # Check last 8 messages
    tool_msg_count = sum(1 for m in recent if m.get("role") == "tool")
    assistant_count = sum(
        1 for m in recent
        if m.get("role") == "assistant" and (m.get("tool_calls") or _has_tool_call_content(m))
    )

    if tool_msg_count >= 2 and assistant_count >= 2:
        return True

    # Check for OpenCode tool names in content
    for m in recent:
        content = m.get("content", "")
        if isinstance(content, str):
            for sig in _OPENCODE_TOOL_SIGNATURES:
                if sig in content.lower():
                    return True

    return False


def _has_tool_call_content(msg: dict) -> bool:
    """Check if message content contains tool call blocks."""
    content = msg.get("content", "")
    if isinstance(content, list):
        return any(
            isinstance(b, dict) and b.get("type") in ("tool_use", "tool_call")
            for b in content
        )
    return False


def get_opencode_injection(
    backend: str,
    tools: list[dict] | None,
    system_prompt: str = "",
) -> str:
    """获取 OpenCode 感知的系统提示注入文本（不修改 messages）。

    用于 skills_injector.py 等需要返回注入文本而非修改消息列表的场景。

    Returns:
        要注入的文本，若无需注入则为空字符串。
    """
    strength = classify_backend_strength(backend)

    parts: list[str] = []

    tool_summary = build_tool_summary(tools)
    if tool_summary:
        parts.append(tool_summary)

    parts.append(_OPENCODE_CODING_CONVENTIONS)

    if strength == "weak":
        parts.append(_THINK_STEP_BY_STEP_PROMPT)

    if strength == "code_specialized":
        parts.append(
            "\n## Code Quality Requirements\n"
            "- Write production-quality, well-typed code.\n"
            "- Include proper error handling and edge case coverage.\n"
            "- Use modern language features where appropriate.\n"
            "- Add brief comments for complex logic only.\n"
        )

    return "\n".join(parts) if parts else ""
