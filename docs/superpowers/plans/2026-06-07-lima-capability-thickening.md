# LiMa 能力加厚实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 三个方向增强 LiMa — 代码质量收尾、Hermes Agent 全能力、智能模型分级路由

**Architecture:** 不改动现有路由管线结构。代码质量聚焦 routing duality 收敛和最大的单体模块拆分；Hermes Agent 实现 Gateway API 真实调用替代占位符；分级路由在 routing_classifier 新增难度评估层，routing_selector 按难度选择模型梯队。

**Tech Stack:** Python 3.10, FastAPI, httpx, OpenAI SDK, Hermes Agent v0.14.0 Gateway API

---

## 子项目 1: 代码质量收尾

### Task 1.1: opencode_tool_splitter.py 拆分（423行 → ≤300行）

**Files:**
- Modify: `opencode_tool_splitter.py`
- Create: `opencode_tool_patterns.py`

**当前状态:** `opencode_tool_splitter.py` 423行，包含工具调用拆分 + 模式匹配 + JSON修复逻辑，可提取模式匹配为独立模块。

- [ ] **Step 1: 创建 `opencode_tool_patterns.py`**

将 `opencode_tool_splitter.py` 中的模式匹配函数提取：

```python
"""Tool call detection patterns for OpenCode integration."""

from __future__ import annotations

import re
from typing import Any

# ── Pattern registry ──────────────────────────────────────────

TOOL_CALL_PATTERNS: list[tuple[re.Pattern, str]] = [
    # OpenAI native tool_calls format
    (re.compile(r'"tool_calls"\s*:\s*\[', re.I), "openai_native"),
    # Anthropic tool_use format
    (re.compile(r'"type"\s*:\s*"tool_use"', re.I), "anthropic_tool_use"),
    # Plain function_call (legacy)
    (re.compile(r'"name"\s*:\s*"[^"]+"\s*,\s*"arguments"\s*:', re.I), "function_call"),
]


def detect_tool_block(text: str) -> str | None:
    """Return pattern name if text contains tool call markers, else None."""
    for pattern, name in TOOL_CALL_PATTERNS:
        if pattern.search(text):
            return name
    return None


def split_tool_lines(text: str) -> tuple[list[str], list[str]]:
    """Split response into tool_call lines and text lines.
    
    Returns (tool_lines, text_lines).
    """
    tool_lines: list[str] = []
    text_lines: list[str] = []
    in_tool = False
    brace_depth = 0

    for line in text.split("\n"):
        stripped = line.strip()
        if detect_tool_block(stripped) or (
            in_tool and stripped and not stripped.startswith("//")
        ):
            in_tool = True
            tool_lines.append(line)
            brace_depth += stripped.count("{") - stripped.count("}")
            if brace_depth <= 0 and in_tool and stripped.endswith("}"):
                in_tool = False
        else:
            text_lines.append(line)

    return tool_lines, text_lines
```

- [ ] **Step 2: 更新 `opencode_tool_splitter.py` 导入新模块**

从 `opencode_tool_patterns` 导入，移除原地模式定义：

```python
# 在 opencode_tool_splitter.py 顶部替换原有模式匹配代码
from opencode_tool_patterns import detect_tool_block, split_tool_lines
```

- [ ] **Step 3: 运行测试验证**

```powershell
.venv310\Scripts\python.exe -m pytest tests/test_opencode_streaming.py tests/test_opencode_tool_splitter.py -v --tb=short
```

- [ ] **Step 4: ruff 检查**

```powershell
ruff check opencode_tool_splitter.py opencode_tool_patterns.py
ruff format opencode_tool_splitter.py opencode_tool_patterns.py
```

- [ ] **Step 5: Commit**

```bash
git add opencode_tool_splitter.py opencode_tool_patterns.py
git commit -m "refactor: extract tool call patterns from opencode_tool_splitter (423→<300 lines)"
```

---

### Task 1.2: smart_router 残余调用方迁移

**Files:**
- Modify: `routing_facade.py`
- Modify: `routes/chat_handler_dispatch.py`（如有残余引用）
- Check: `smart_router.py`（确认仅剩的 3 个调用方可安全迁移）

**当前状态:** `STATUS.md` 记录 smart_router 生产引用 14→3，需确认剩余调用方并迁移。

- [ ] **Step 1: 定位剩余调用方**

```powershell
rg -n "from smart_router|import smart_router" routes/ routing_facade.py routing_engine.py --glob '*.py'
```

- [ ] **Step 2: 逐一迁移**

对每个调用方：
1. 理解当前调用 `smart_router.xxx()` 的目的
2. 找到 `routing_engine` / `routing_facade` 中对应函数
3. 替换 import 和调用
4. 确保行为一致

- [ ] **Step 3: 运行完整测试套件**

```powershell
.venv310\Scripts\python.exe -m pytest tests/test_routing_engine.py tests/test_routing_facade.py -v --tb=short
.venv310\Scripts\python.exe -m pytest tests/ -q --tb=short -k "routing"
```

- [ ] **Step 4: 更新 smart_router.py docstring**

标记为 legacy compat only：

```python
"""Legacy routing utilities — maintained for backward compatibility.
   
   All new code should use routing_engine.route() directly.
   This module is NOT the production routing authority.
   
   Remaining callers: 0 (fully migrated as of 2026-06-07)
"""
```

- [ ] **Step 5: 更新 STATUS.md**

```bash
git add routing_facade.py smart_router.py STATUS.md
git commit -m "refactor: complete smart_router migration (3→0 remaining callers)"
```

---

## 子项目 2: Hermes Agent 全能力

### Task 2.1: 实现 Hermes Gateway API 客户端

**Files:**
- Modify: `hermes_bridge.py`
- Create: `hermes_gateway.py`

**当前状态:** `call_hermes_agent()` 是占位符，实际调用 `call_lima_structured()`。Hermes v0.14.0 支持 Gateway 模式（持久化服务端 + 消息 API），需要实现真实调用。

- [ ] **Step 1: 创建 `hermes_gateway.py`**

```python
"""Hermes Agent Gateway API client (Mode 3: true agent execution)."""

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any

logger = logging.getLogger(__name__)

HERMES_GATEWAY_PORT = int(os.environ.get("HERMES_GATEWAY_PORT", "18790"))
HERMES_GATEWAY_BASE = f"http://127.0.0.1:{HERMES_GATEWAY_PORT}"


def _check_gateway() -> bool:
    """Check if Hermes Gateway is running."""
    import urllib.request
    try:
        req = urllib.request.Request(
            f"{HERMES_GATEWAY_BASE}/health",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


def send_agent_task(
    prompt: str,
    *,
    task_type: str = "chat",
    model: str = "lima-1.3",
    toolsets: list[str] | None = None,
    timeout: int = 120,
) -> dict[str, Any]:
    """Send a task to Hermes Agent Gateway for autonomous execution.

    Args:
        prompt: The task prompt.
        task_type: 'code_exec', 'file_ops', 'browser', 'research', 'chat'.
        model: Model to use (default: LiMa via custom:lima).
        toolsets: Tool categories to enable. None = auto-detect.
        timeout: Max execution time in seconds.

    Returns:
        Dict with keys: 'response', 'task_id', 'tool_calls', 'steps', 'success'.
    """
    if not _check_gateway():
        raise RuntimeError("Hermes Gateway not reachable on port " + str(HERMES_GATEWAY_PORT))

    import urllib.request

    task_id = f"lima-{uuid.uuid4().hex[:8]}"
    body = json.dumps({
        "task_id": task_id,
        "prompt": prompt,
        "task_type": task_type,
        "model": model,
        "toolsets": toolsets or _default_toolsets(task_type),
        "max_turns": 20,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{HERMES_GATEWAY_BASE}/tasks",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.exception("hermes_gateway: task failed")
        return {
            "response": f"[Hermes Gateway Error: {e}]",
            "task_id": task_id,
            "tool_calls": [],
            "steps": 0,
            "success": False,
        }

    return {
        "response": data.get("response", ""),
        "task_id": task_id,
        "tool_calls": data.get("tool_calls", []),
        "steps": data.get("steps", 0),
        "success": data.get("success", True),
    }


def _default_toolsets(task_type: str) -> list[str]:
    """Map task type to default tool categories."""
    mapping = {
        "code_exec": ["shell", "file"],
        "file_ops": ["file"],
        "browser": ["browser", "file"],
        "research": ["web", "file"],
        "chat": [],
    }
    return mapping.get(task_type, [])
```

- [ ] **Step 2: 更新 `hermes_bridge.py` 的 `call_hermes_agent()`**

替换占位符实现：

```python
def call_hermes_agent(
    prompt: str,
    *,
    task_type: str = "chat",
    extract_tools: bool = False,
    **kwargs,
) -> dict:
    """Call Hermes Agent for autonomous task execution (Mode 3).

    Uses Hermes Gateway API when available, falls back to structured lima call.
    """
    # Try Hermes Gateway first (real agent execution)
    try:
        from hermes_gateway import send_agent_task, _check_gateway
        if _check_gateway():
            result = send_agent_task(prompt, task_type=task_type, **kwargs)
            if result.get("success"):
                logger.info(
                    "hermes_agent: gateway task complete steps=%d",
                    result.get("steps", 0),
                )
                if extract_tools:
                    tools = extract_tool_calls(result.get("response", ""))
                    if tools:
                        result["tool_calls"] = tools
                return result
    except (ImportError, RuntimeError) as e:
        logger.debug("hermes_agent: gateway not available (%s), falling back", e)

    # Fallback: structured lima call (current behavior)
    result = call_lima_structured(task_type, prompt, **kwargs)
    if extract_tools:
        tools = extract_tool_calls(result.get("response", ""))
        if tools:
            result["tool_calls"] = tools
            logger.info("hermes_agent: extracted %d tool calls", len(tools))
    return result
```

- [ ] **Step 3: 启动 Hermes Gateway 并测试**

在 VPS 上启动 Hermes Gateway：

```bash
# VPS 上执行
nohup hermes gateway --port 18790 --provider custom:lima --model lima-1.3 > /var/log/hermes-gateway.log 2>&1 &
```

验证 Gateway 可用：

```bash
curl -sf http://127.0.0.1:18790/health
```

- [ ] **Step 4: 创建 systemd service 文件**

```ini
# /etc/systemd/system/hermes-gateway.service
[Unit]
Description=Hermes Agent Gateway
After=network.target lima-router.service

[Service]
Type=simple
ExecStart=/usr/local/bin/hermes gateway --port 18790 --provider custom:lima --model lima-1.3
Restart=always
RestartSec=5
Environment=HOME=/root
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 5: 部署并验证**

```bash
# VPS 上执行
systemctl daemon-reload
systemctl enable hermes-gateway
systemctl start hermes-gateway
systemctl status hermes-gateway
```

- [ ] **Step 6: 设置环境变量启用 Agent**

```bash
# 在 VPS /opt/lima-router/.env 追加
echo 'HERMES_AGENT_ENABLED=1' >> /opt/lima-router/.env
echo 'HERMES_GATEWAY_PORT=18790' >> /opt/lima-router/.env
systemctl restart lima-router
```

- [ ] **Step 7: 端到端 Agent 测试**

```python
# 测试脚本 test_hermes_agent_e2e.py
import sys
sys.path.insert(0, "/opt/lima-router")
from hermes_bridge import call_hermes_agent

result = call_hermes_agent(
    "Create a file /tmp/hello.txt with content 'Hello from Hermes Agent'",
    task_type="file_ops",
    extract_tools=True,
)
print(f"success={result.get('success')}")
print(f"steps={result.get('steps', 0)}")
print(f"tool_calls={len(result.get('tool_calls', []))}")
```

- [ ] **Step 8: Commit**

```bash
git add hermes_bridge.py hermes_gateway.py
git commit -m "feat: implement Hermes Agent Gateway API client (Mode 3 real execution)"
```

---

### Task 2.2: 确保 hermes_agent 后端健康检查正常工作

**Files:**
- Modify: `hermes_api.py`（确认 `/health` 端点返回正确）

**当前状态:** `hermes_api.py` 已有 `/health` 端点返回 `{"status": "ok"}`。需确认 LiMa 的 health_tracker 能正确探测 `hermes_agent` 后端。

- [ ] **Step 1: 验证 hermes_api health 端点**

```bash
curl -sf http://127.0.0.1:8699/health
# Expected: {"status":"ok","model":"hermes-agent","port":8699}
```

- [ ] **Step 2: 验证 LiMa 后端探测**

```bash
# 在 LiMa 日志中确认 hermes_agent 被探测
journalctl -u lima-router --since "1 min ago" | grep hermes_agent
```

- [ ] **Step 3: 确认 STATUS.md 中部署状态表包含 hermes 服务**

无需 commit（验证步骤）。

---

## 子项目 3: 智能模型分级路由

### Task 3.1: 任务难度评估器

**Files:**
- Modify: `routing_classifier.py`
- Create: `routing_difficulty.py`

- [ ] **Step 1: 创建 `routing_difficulty.py`**

```python
"""Task difficulty estimation for tiered model routing.

Estimates coding task complexity on a 0-100 scale to route:
- Simple tasks (0-30) → free/budget models
- Medium tasks (30-70) → mid-tier models  
- Hard tasks (70-100) → premium models
"""

from __future__ import annotations


def estimate_difficulty(query: str, messages: list[dict], *,
                        scenario: str = "") -> int:
    """Return difficulty score 0-100 based on task signals.
    
    0 = trivial (single-line fix, simple question)
    50 = moderate (feature implementation, bug fix)
    100 = very hard (architecture design, multi-system integration)
    """
    score = 0

    # Extract last user text
    text = _extract_last_user_text(query, messages)

    # ── Complexity signals (each adds weighted points) ──

    # Multi-file / large scope
    if any(s in text for s in ("refactor", "migrate", "restructure", "redesign")):
        score += 25
    if any(s in text for s in ("entire project", "across all", "every file")):
        score += 20
    if any(s in text for s in ("multiple files", "several files", "many files")):
        score += 15

    # Architecture / design
    if any(s in text for s in ("architecture", "design pattern", "system design")):
        score += 20
    if any(s in text for s in ("database schema", "data model", "API design")):
        score += 15

    # Algorithm / complexity
    if any(s in text for s in ("algorithm", "optimize", "performance", "concurrent")):
        score += 15
    if any(s in text for s in ("O(n)", "time complexity", "space complexity")):
        score += 10

    # Integration / external systems
    if any(s in text for s in ("integrate", "connect to", "API integration", "webhook")):
        score += 10
    if any(s in text for s in ("docker", "kubernetes", "deploy", "CI/CD")):
        score += 10

    # Code length signals
    code_block_count = text.count("```")
    if code_block_count >= 6:
        score += 15  # Multiple code blocks = complex
    elif code_block_count >= 2:
        score += 5

    # Message count (multi-turn = more context)
    user_msg_count = sum(1 for m in messages if isinstance(m, dict) and m.get("role") == "user")
    if user_msg_count >= 5:
        score += 10  # Long conversation suggests complexity
    elif user_msg_count >= 3:
        score += 5

    # ── Simplicity signals (reduces score) ──

    if any(s in text for s in ("simple", "quick", "one line", "just")):
        score -= 15
    if len(text.split()) < 10:
        score -= 20  # Very short queries

    return max(0, min(100, score))


def _extract_last_user_text(query: str, messages: list[dict]) -> str:
    """Get last user message content as lowercase string."""
    text = query
    if messages:
        for m in reversed(messages):
            if isinstance(m, dict) and m.get("role") == "user":
                content = m.get("content", "")
                if isinstance(content, list):
                    text = " ".join(
                        b.get("text", "") for b in content if isinstance(b, dict))
                elif isinstance(content, str):
                    text = content
                break
    return text.lower()
```

- [ ] **Step 2: 编写单元测试**

创建 `tests/test_routing_difficulty.py`：

```python
import pytest
from routing_difficulty import estimate_difficulty


def test_trivial_query_returns_low_score():
    score = estimate_difficulty("hello", [], scenario="chat")
    assert score < 20


def test_simple_coding_returns_low_score():
    score = estimate_difficulty(
        "just add a print statement",
        [{"role": "user", "content": "just add a print statement"}],
        scenario="coding",
    )
    assert score < 30


def test_refactor_returns_high_score():
    score = estimate_difficulty(
        "refactor the entire authentication module",
        [{"role": "user", "content": "refactor the entire authentication module"}],
        scenario="coding",
    )
    assert score >= 25


def test_architecture_returns_high_score():
    score = estimate_difficulty(
        "design a microservice architecture for the payment system",
        [{"role": "user", "content": "design a microservice architecture for the payment system"}],
        scenario="coding",
    )
    assert score >= 40


def test_multi_turn_boosts_score():
    score = estimate_difficulty(
        "fix this bug",
        [
            {"role": "user", "content": "help"},
            {"role": "assistant", "content": "ok"},
            {"role": "user", "content": "code"},
            {"role": "assistant", "content": "yes"},
            {"role": "user", "content": "refactor everything"},
        ],
        scenario="coding",
    )
    assert score >= 25


def test_short_message_reduces_score():
    score = estimate_difficulty("hi", [], scenario="chat")
    assert score == 0
```

- [ ] **Step 3: 运行测试**

```powershell
.venv310\Scripts\python.exe -m pytest tests/test_routing_difficulty.py -v --tb=short
```

- [ ] **Step 4: Commit**

```bash
git add routing_difficulty.py tests/test_routing_difficulty.py
git commit -m "feat: add task difficulty estimator for tiered routing"
```

---

### Task 3.2: 模型梯队定义与路由集成

**Files:**
- Create: `routing_tiers.py`
- Modify: `routing_selector.py`
- Modify: `routing_classifier.py`

- [ ] **Step 1: 创建 `routing_tiers.py`**

```python
"""Model tier definitions for cost-aware routing.

Tiers:
  FREE    — no API key cost, suitable for simple tasks
  BUDGET  — low-cost, good for everyday coding
  PREMIUM — high-capability, reserved for complex tasks
"""

from __future__ import annotations

# Backend → tier mapping
FREE_BACKENDS: set[str] = {
    "chinamobile",      # MiniMax M25, free
    "longcat_chat",     # LongCat, free tier
    "longcat_lite",
    "ddg_gpt4o_mini",   # DuckDuckGo (if available)
    "github_gpt4o_mini", # GitHub Copilot free
}

BUDGET_BACKENDS: set[str] = {
    "groq_llama8b",
    "groq_llama70b",
    "cerebras_llama8b",
    "cerebras_gptoss",
    "mistral_small",
    "scnet_qwen30b",
    "scnet_ds_flash",
}

PREMIUM_BACKENDS: set[str] = {
    "scnet_ds_pro",
    "scnet_qwen235b",
    "groq_qwen32b",
    "mistral_large",
    "github_gpt4o",
    "cerebras_qwen235b",
    "hermes_agent",     # Agent execution (special)
}

# Any backend not in these sets defaults to BUDGET tier
DEFAULT_TIER = "budget"


def get_tier(backend_name: str) -> str:
    """Return tier name for a backend."""
    if backend_name in FREE_BACKENDS:
        return "free"
    if backend_name in BUDGET_BACKENDS:
        return "budget"
    if backend_name in PREMIUM_BACKENDS:
        return "premium"
    return DEFAULT_TIER


def tier_for_difficulty(difficulty: int) -> str:
    """Map difficulty score (0-100) to target tier."""
    if difficulty <= 30:
        return "free"
    if difficulty <= 70:
        return "budget"
    return "premium"
```

- [ ] **Step 2: 修改 `routing_classifier.py` 添加 `classify_difficulty()`**

在文件末尾添加：

```python
def classify_difficulty(query: str, messages: list[dict], *,
                        scenario: str = "") -> int:
    """Estimate coding task difficulty for tiered model selection.
    
    Returns 0-100 score. Call after classify_scenario() for coding tasks.
    """
    if scenario != "coding":
        return 0
    from routing_difficulty import estimate_difficulty
    return estimate_difficulty(query, messages, scenario=scenario)
```

- [ ] **Step 3: 修改 `routing_selector.py` 集成难度分级**

在 `select()` 函数中，评分循环之前添加难度感知的 tier 加分：

```python
# 在 routing_selector.py 开头添加导入
from routing_tiers import get_tier, tier_for_difficulty

# 在 select() 函数中，sticky_session 检查之后、评分循环之前添加:
# ── Tiered model routing: boost backends matching task difficulty ──
if scenario == "coding":
    try:
        from routing_classifier import classify_difficulty
        difficulty = classify_difficulty("", [], scenario="coding")  # placeholder
    except ImportError:
        difficulty = 50  # default moderate

    target_tier = tier_for_difficulty(difficulty)
    _TIER_BOOST = {"free": 1.3, "budget": 1.0, "premium": 1.3}

    # Apply tier boost during scoring loop (after existing scoring logic)
    # Add this inside the for-loop:
    # tier = get_tier(b)
    # if tier == target_tier:
    #     scores[b] *= _TIER_BOOST.get(tier, 1.0)
```

**注意:** 实际实现需要将 difficulty 计算移到 `routing_engine.py` 的调用处传入 `select()`，而不是在 selector 内重新计算。修改 `select()` 签名添加 `difficulty: int = 50` 参数。

- [ ] **Step 4: 修改 `routing_engine.py` 传递 difficulty**

在 `routing_engine.py` 的 `route()` 函数中，classification 之后添加 difficulty 计算：

```python
# After: scenario = classify_scenario(...)
# Add:
if scenario == "coding":
    difficulty = classify_difficulty(query, messages, scenario=scenario)
else:
    difficulty = 0

# Then pass to select():
backends = select(request_type, health_map, ..., difficulty=difficulty)
```

- [ ] **Step 5: 运行测试**

```powershell
.venv310\Scripts\python.exe -m pytest tests/test_routing_engine.py tests/test_routing_difficulty.py -v --tb=short
```

- [ ] **Step 6: 编写分级路由集成测试**

```python
# tests/test_routing_tiers.py
from routing_tiers import get_tier, tier_for_difficulty


def test_free_tier_for_known_free_backend():
    assert get_tier("chinamobile") == "free"
    assert get_tier("longcat_chat") == "free"


def test_premium_tier_for_known_premium_backend():
    assert get_tier("scnet_ds_pro") == "premium"
    assert get_tier("hermes_agent") == "premium"


def test_unknown_backend_defaults_to_budget():
    assert get_tier("some_unknown_backend") == "budget"


def test_low_difficulty_maps_to_free():
    assert tier_for_difficulty(10) == "free"
    assert tier_for_difficulty(30) == "free"


def test_medium_difficulty_maps_to_budget():
    assert tier_for_difficulty(50) == "budget"


def test_high_difficulty_maps_to_premium():
    assert tier_for_difficulty(80) == "premium"
    assert tier_for_difficulty(100) == "premium"
```

- [ ] **Step 7: Commit**

```bash
git add routing_tiers.py routing_classifier.py routing_selector.py routing_engine.py tests/test_routing_tiers.py
git commit -m "feat: tiered model routing based on task difficulty estimation"
```

---

## 子项目 4: 端到端验证与部署

### Task 4.1: 全量测试 + VPS 部署

**Files:**
- Deploy: `opencode_tool_patterns.py`, `hermes_gateway.py`, `routing_difficulty.py`, `routing_tiers.py`
- Update: `opencode_tool_splitter.py`, `hermes_bridge.py`, `routing_classifier.py`, `routing_selector.py`, `routing_engine.py`

- [ ] **Step 1: 本地全量测试**

```powershell
.venv310\Scripts\python.exe -m pytest tests/ -q --tb=short -m "not rag_gate"
```

- [ ] **Step 2: Lint 检查**

```powershell
ruff check opencode_tool_patterns.py hermes_gateway.py routing_difficulty.py routing_tiers.py
ruff format --check opencode_tool_patterns.py hermes_gateway.py routing_difficulty.py routing_tiers.py
```

- [ ] **Step 3: VPS 部署**

```bash
# 使用 lima-deploy skill 部署
# 上传新文件 + 重启 lima-router
```

- [ ] **Step 4: VPS Health 检查**

```bash
curl -sf https://chat.donglicao.com/health
# Expected: 200 OK, hermes_agent 在模块列表中
```

- [ ] **Step 5: VPS Smoke 测试**

```bash
# Agent task 测试
curl -s -X POST https://chat.donglicao.com/v1/chat/completions \
  -H "Authorization: Bearer $LIMA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"lima-1.3","messages":[{"role":"user","content":"create a file /tmp/test.txt with content hello"}]}' | python -m json.tool

# 验证路由到 hermes_agent（检查 x_lima_meta 中的 backend）
```

- [ ] **Step 6: 更新 STATUS.md + progress.md**

- [ ] **Step 7: Commit + Push**

```bash
git add STATUS.md progress.md
git commit -m "feat: LiMa capability thickening complete — tiered routing + Hermes Agent + code quality"
git push origin HEAD
```

---

## 验收标准

| 子项目 | 验收项 | 标准 |
|--------|--------|------|
| 1. 代码质量 | opencode_tool_splitter 行数 | ≤300 行 |
| 1. 代码质量 | smart_router 剩余调用方 | 0 |
| 1. 代码质量 | 测试通过率 | 100%（现有测试） |
| 2. Hermes Agent | hermes-gateway.service | active + health OK |
| 2. Hermes Agent | Agent 任务 E2E | curl 请求返回正确响应 |
| 2. Hermes Agent | 环境变量 | `HERMES_AGENT_ENABLED=1` |
| 3. 分级路由 | 难度评估测试 | 6/6 PASS |
| 3. 分级路由 | 梯队定义测试 | 6/6 PASS |
| 3. 分级路由 | routing selector 集成 | 不破坏现有 196 个路由测试 |
| 4. E2E | VPS 部署 | lima-router active + health OK |
| 4. E2E | VPS smoke | /v1/chat/completions 200 OK |
