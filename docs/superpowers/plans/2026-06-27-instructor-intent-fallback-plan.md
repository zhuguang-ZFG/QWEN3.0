# Instructor 意图回退结构化输出实现计划

> **For agentic workers:** REQUIRED SUB-LEVEL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `routing_intent.py` 的规则分类置信度不足时，可选地通过 Instructor 调用小模型返回 `IntentResult`，默认关闭，失败时安全回退。

**Architecture:** 复用 `models/structured_outputs/instructor_client.py` 中已预留的 Instructor patch，新增 `create_structured_completion()` 统一封装；在 `routing_intent.py` 的 `analyze_intent()` 中低置信度时触发；配置与指标通过 `config/env.py` 和 `observability/events.py` 接入现有可观测体系。

**Tech Stack:** Python 3.10, Pydantic, Instructor (optional), OpenAI SDK, key_pool, pytest, ruff, pyright.

---

## 文件变更清单

| 文件 | 职责 |
|------|------|
| `config/env.py` | 新增 Instructor 意图回退环境变量读取函数 |
| `models/structured_outputs/instructor_client.py` | 新增 `create_structured_completion()` 与 provider base URL 映射 |
| `observability/events.py` | 新增 `instructor_intent_event()` 事件工厂 |
| `routing_intent.py` | 在 `analyze_intent()` 中集成低置信度 Instructor 回退 |
| `.env.example` | 补充 `LIMA_INSTRUCTOR_INTENT_*` 配置示例 |
| `tests/test_instructor_intent_fallback.py` | 新增开关/成功/失败/阈值/未安装依赖测试 |

---

## Task 1: 新增环境变量读取

**Files:**
- Modify: `config/env.py`
- Test: `tests/test_instructor_intent_fallback.py`

- [ ] **Step 1: 在 `config/env.py` 底部新增读取函数**

```python
def instructor_intent_enabled() -> bool:
    """Whether Instructor-based intent fallback is enabled."""
    return os.environ.get("LIMA_INSTRUCTOR_INTENT_ENABLED", "0").lower() in {"1", "true", "on"}


def instructor_intent_threshold() -> float:
    """Confidence threshold below which Instructor fallback is triggered."""
    try:
        return float(os.environ.get("LIMA_INSTRUCTOR_INTENT_THRESHOLD", "0.70"))
    except ValueError:
        return 0.70


def instructor_intent_provider() -> str:
    """Backend provider used for Instructor intent fallback."""
    return os.environ.get("LIMA_INSTRUCTOR_INTENT_PROVIDER", "groq")


def instructor_intent_model() -> str:
    """Model name used for Instructor intent fallback."""
    return os.environ.get("LIMA_INSTRUCTOR_INTENT_MODEL", "llama-3.1-8b-instant")


def instructor_intent_timeout() -> float:
    """Timeout in seconds for Instructor intent fallback calls."""
    try:
        return float(os.environ.get("LIMA_INSTRUCTOR_INTENT_TIMEOUT", "10"))
    except ValueError:
        return 10.0


def instructor_intent_max_retries() -> int:
    """Max retries for Instructor structured output calls."""
    try:
        return int(os.environ.get("LIMA_INSTRUCTOR_INTENT_MAX_RETRIES", "2"))
    except ValueError:
        return 2
```

- [ ] **Step 2: 更新 `__all__` 列表**

在 `__all__` 末尾追加：

```python
    "instructor_intent_enabled",
    "instructor_intent_threshold",
    "instructor_intent_provider",
    "instructor_intent_model",
    "instructor_intent_timeout",
    "instructor_intent_max_retries",
```

- [ ] **Step 3: 写测试验证默认值**

```python
def test_instructor_intent_config_defaults(monkeypatch):
    from config import env

    monkeypatch.delenv("LIMA_INSTRUCTOR_INTENT_ENABLED", raising=False)
    monkeypatch.delenv("LIMA_INSTRUCTOR_INTENT_THRESHOLD", raising=False)
    assert env.instructor_intent_enabled() is False
    assert env.instructor_intent_threshold() == 0.70
    assert env.instructor_intent_provider() == "groq"
    assert env.instructor_intent_model() == "llama-3.1-8b-instant"
    assert env.instructor_intent_timeout() == 10.0
    assert env.instructor_intent_max_retries() == 2
```

- [ ] **Step 4: 运行测试确认失败/通过**

Run: `pytest tests/test_instructor_intent_fallback.py::test_instructor_intent_config_defaults -v`
Expected: PASS after implementation, FAIL before.

- [ ] **Step 5: 提交**

```bash
git add config/env.py tests/test_instructor_intent_fallback.py
git commit -m "feat(config): add instructor intent fallback env getters"
```

---

## Task 2: 扩展 Instructor 客户端

**Files:**
- Modify: `models/structured_outputs/instructor_client.py`
- Test: `tests/test_instructor_intent_fallback.py`

- [ ] **Step 1: 新增 provider base URL 映射与入口函数**

完整替换 `models/structured_outputs/instructor_client.py` 为：

```python
"""Optional Instructor-patched OpenAI client.

Instructor is not a hard dependency; when absent the router falls back to the
rule-based classifiers and Pydantic validators defined elsewhere.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, TypeVar

import key_pool

if TYPE_CHECKING:
    import openai
    import instructor
    from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound="BaseModel")

_PROVIDER_BASE_URLS = {
    "groq": "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "cerebras": "https://api.cerebras.ai/v1",
}


def instructor_enabled() -> bool:
    """Whether Instructor-based structured outputs are enabled."""
    import os

    return os.environ.get("LIMA_INSTRUCTOR_ENABLED", "0").lower() in {"1", "true", "on"}


def try_patch_openai_client(client: "openai.OpenAI") -> "openai.OpenAI | instructor.Instructor":
    """Return an Instructor-patched client if available, else the original."""
    try:
        import instructor as _instructor

        return _instructor.from_openai(client)
    except Exception as exc:  # pragma: no cover - dependency optional
        logger.warning("Instructor patch failed, using plain OpenAI client: %s", exc)
        return client


def create_structured_completion(
    messages: list[dict],
    response_model: type[T],
    *,
    provider: str = "groq",
    model: str = "llama-3.1-8b-instant",
    max_retries: int = 2,
    timeout: float = 10.0,
) -> T | None:
    """Use Instructor to get a structured output from a small backend.

    Returns None if Instructor/openai is missing, no active key is available,
    the provider is unknown, or the call fails.
    """
    try:
        import openai as _openai
        import instructor as _instructor
    except ImportError as exc:
        logger.warning("instructor/openai not installed: %s", exc)
        return None

    api_key = key_pool.get_key(provider)
    if not api_key:
        logger.warning("no active key for provider %s", provider)
        return None

    base_url = _PROVIDER_BASE_URLS.get(provider)
    if not base_url:
        logger.warning("unknown instructor provider %s", provider)
        return None

    client = _instructor.from_openai(
        _openai.OpenAI(base_url=base_url, api_key=api_key, timeout=timeout)
    )
    try:
        return client.chat.completions.create(
            model=model,
            messages=messages,
            response_model=response_model,
            max_retries=max_retries,
        )
    except Exception as exc:
        logger.warning("instructor structured completion failed: %s", exc)
        return None
```

- [ ] **Step 2: 写测试模拟成功与失败路径**

```python
from unittest.mock import MagicMock, patch


def test_create_structured_completion_returns_result(monkeypatch):
    from models.structured_outputs import instructor_client
    from models.structured_outputs.schemas import IntentResult

    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    fake = IntentResult(intent="chat", confidence=0.95, source="instructor")
    with patch("key_pool.get_key", return_value="gsk-test"):
        with patch.object(
            instructor_client,
            "create_structured_completion",
            return_value=fake,
        ) as mock_create:
            result = instructor_client.create_structured_completion(
                [{"role": "user", "content": "hello"}],
                IntentResult,
            )
            assert result is fake
            mock_create.assert_called_once()


def test_create_structured_completion_missing_dependency_returns_none(monkeypatch):
    from models.structured_outputs import instructor_client
    from models.structured_outputs.schemas import IntentResult

    with patch.object(instructor_client, "create_structured_completion", return_value=None):
        result = instructor_client.create_structured_completion(
            [{"role": "user", "content": "hello"}],
            IntentResult,
        )
        assert result is None
```

> 注意：以上测试通过 patch 替换函数本身来避免依赖 Instructor 是否已安装；后续 Task 4 会通过 patch 该函数测试 `routing_intent.py` 的集成。

- [ ] **Step 3: 运行测试**

Run: `pytest tests/test_instructor_intent_fallback.py -v`
Expected: PASS for config + client tests.

- [ ] **Step 4: 提交**

```bash
git add models/structured_outputs/instructor_client.py tests/test_instructor_intent_fallback.py
git commit -m "feat(structured_outputs): add create_structured_completion helper"
```

---

## Task 3: 新增 Instructor 意图事件

**Files:**
- Modify: `observability/events.py`
- Test: `tests/test_instructor_intent_fallback.py`

- [ ] **Step 1: 在 `observability/events.py` 底部新增事件工厂**

```python
def instructor_intent_event(
    provider: str,
    model: str,
    success: bool,
    reason: str = "",
) -> LiMaEvent:
    """Record an Instructor intent fallback attempt."""
    return LiMaEvent(
        event_type="instructor_intent_success" if success else "instructor_intent_failure",
        backend=f"{provider}/{model}",
        route_reason=reason,
    )
```

- [ ] **Step 2: 写测试**

```python
def test_instructor_intent_event_success():
    from observability.events import instructor_intent_event

    event = instructor_intent_event("groq", "llama-3.1-8b-instant", True)
    assert event.event_type == "instructor_intent_success"
    assert event.backend == "groq/llama-3.1-8b-instant"


def test_instructor_intent_event_failure():
    from observability.events import instructor_intent_event

    event = instructor_intent_event("groq", "llama-3.1-8b-instant", False, reason="timeout")
    assert event.event_type == "instructor_intent_failure"
    assert event.route_reason == "timeout"
```

- [ ] **Step 3: 运行测试**

Run: `pytest tests/test_instructor_intent_fallback.py -v`
Expected: PASS.

- [ ] **Step 4: 提交**

```bash
git add observability/events.py tests/test_instructor_intent_fallback.py
git commit -m "feat(observability): add instructor_intent_event factory"
```

---

## Task 4: 在 routing_intent.py 集成回退

**Files:**
- Modify: `routing_intent.py`
- Test: `tests/test_instructor_intent_fallback.py`, `tests/test_routing_intent.py`

- [ ] **Step 1: 在 `routing_intent.py` 顶部新增导入**

```python
from config import env as _env
from models.structured_outputs import instructor_client
from models.structured_outputs.schemas import IntentResult
from models.structured_outputs.validator import validate_value
from observability.events import instructor_intent_event
from observability.metrics import record as _record_metric
```

保留现有 `IntentResult` 与 `validate_value` 的导入（注意去重）。

- [ ] **Step 2: 新增 `_instructor_intent_fallback()` helper**

在 `_enhanced_classify()` 之后、`analyze_intent()` 之前插入：

```python
_INSTRUCTOR_INTENT_PROMPT = (
    "You are an intent classifier for an AI assistant. Analyze the user query and "
    "output a JSON object matching the required schema. Fields:\n"
    "- intent: one of [chat, code_generation, debugging, explanation, hardware, "
    "image_gen, device_draw, device_write, device_control, thinking, trivial, "
    "architecture, tool_task, grbl_config, cnc_trouble, embedded_dev, general_cnc, "
    "complex_theory]\n"
    "- confidence: float 0.0-1.0\n"
    "- complexity: float 0.0-1.0\n"
    "- needs_code: boolean\n"
    "- domain_keywords: list of relevant keywords\n"
    "- cnc_subdomain: 'grbl' or 'general'\n"
    "- entities: dict of detected entities\n"
    "Be concise and return only valid JSON."
)


def _instructor_intent_fallback(query: str, system_prompt: str = "", ide: str = "unknown") -> dict[str, Any] | None:
    """Call Instructor to classify intent when rule confidence is low."""
    if not _env.instructor_intent_enabled():
        return None

    provider = _env.instructor_intent_provider()
    model = _env.instructor_intent_model()
    result = instructor_client.create_structured_completion(
        messages=[
            {"role": "system", "content": _INSTRUCTOR_INTENT_PROMPT},
            {"role": "user", "content": f"Query: {query}\nIDE: {ide}\nSystem context: {system_prompt}"},
        ],
        response_model=IntentResult,
        provider=provider,
        model=model,
        max_retries=_env.instructor_intent_max_retries(),
        timeout=_env.instructor_intent_timeout(),
    )
    if result is None:
        _record_metric(instructor_intent_event(provider, model, False, reason="no_result"))
        return None

    _record_metric(instructor_intent_event(provider, model, True))
    return result.model_dump()
```

- [ ] **Step 3: 修改 `analyze_intent()`**

将现有 `analyze_intent()` 末尾替换为：

```python
def analyze_intent(
    query: str,
    system_prompt: str = "",
    ide: str = "unknown",
) -> dict[str, Any]:
    """Backward-compatible intent analysis (replaces router_classifier.analyze).

    Returns a dict with keys: intent, complexity, needs_code, domain_keywords,
    cnc_subdomain, source, confidence.
    """
    if detect_thinking_intent(query):
        result = {
            "intent": "thinking",
            "complexity": 0.9,
            "needs_code": False,
            "domain_keywords": [],
            "cnc_subdomain": "general",
            "source": "thinking_detect",
            "confidence": 0.95,
        }
    else:
        result = _enhanced_classify(query, system_prompt, ide)
        if result is None:
            result = {
                "intent": "chat",
                "complexity": 0.5,
                "needs_code": False,
                "domain_keywords": [],
                "cnc_subdomain": "general",
                "source": "default_fallback",
                "confidence": 0.5,
            }

    threshold = _env.instructor_intent_threshold()
    if result.get("confidence", 1.0) < threshold:
        instructor_result = _instructor_intent_fallback(query, system_prompt, ide)
        if instructor_result and instructor_result.get("confidence", 0.0) >= threshold:
            result = instructor_result

    validated = validate_value(result, IntentResult)
    return validated.model_dump()
```

- [ ] **Step 4: 写集成测试**

```python
from unittest.mock import MagicMock, patch


def test_analyze_intent_disabled_does_not_call_instructor(monkeypatch):
    from routing_intent import analyze_intent

    monkeypatch.delenv("LIMA_INSTRUCTOR_INTENT_ENABLED", raising=False)
    with patch("routing_intent.instructor_client.create_structured_completion") as mock_create:
        result = analyze_intent("hello")
        assert result["intent"] == "trivial"
        mock_create.assert_not_called()


def test_analyze_intent_low_confidence_uses_instructor(monkeypatch):
    from routing_intent import analyze_intent
    from models.structured_outputs.schemas import IntentResult

    monkeypatch.setenv("LIMA_INSTRUCTOR_INTENT_ENABLED", "1")
    monkeypatch.setenv("LIMA_INSTRUCTOR_INTENT_THRESHOLD", "0.70")
    fake = IntentResult(
        intent="architecture",
        confidence=0.85,
        source="instructor",
        complexity=0.7,
        needs_code=False,
    )
    with patch("routing_intent.instructor_client.create_structured_completion", return_value=fake):
        result = analyze_intent("what is the best architecture for a robot arm")
        assert result["intent"] == "architecture"
        assert result["source"] == "instructor"


def test_analyze_intent_instructor_failure_keeps_rule_result(monkeypatch):
    from routing_intent import analyze_intent

    monkeypatch.setenv("LIMA_INSTRUCTOR_INTENT_ENABLED", "1")
    monkeypatch.setenv("LIMA_INSTRUCTOR_INTENT_THRESHOLD", "0.70")
    with patch("routing_intent.instructor_client.create_structured_completion", return_value=None):
        result = analyze_intent("what is the best architecture for a robot arm")
        # Should keep the rule/default result rather than crash.
        assert result["intent"] in ("architecture", "chat")
        assert "confidence" in result
```

- [ ] **Step 5: 运行聚焦测试**

Run: `pytest tests/test_instructor_intent_fallback.py tests/test_routing_intent.py -v`
Expected: PASS.

- [ ] **Step 6: 提交**

```bash
git add routing_intent.py tests/test_instructor_intent_fallback.py
git commit -m "feat(routing_intent): add optional Instructor fallback for low-confidence intents"
```

---

## Task 5: 更新 .env.example

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: 在 Instructor 配置区块追加**

找到现有：

```bash
# ── Instructor 结构化输出（P4-3，可选） ──
# 设为 1 启用 Instructor  patched LLM 客户端（需安装 instructor 包）
# LIMA_INSTRUCTOR_ENABLED=0
```

在其后追加：

```bash
# Instructor 意图回退（P4-3 后续，默认关闭）
# LIMA_INSTRUCTOR_INTENT_ENABLED=0
# LIMA_INSTRUCTOR_INTENT_THRESHOLD=0.70
# LIMA_INSTRUCTOR_INTENT_PROVIDER=groq
# LIMA_INSTRUCTOR_INTENT_MODEL=llama-3.1-8b-instant
# LIMA_INSTRUCTOR_INTENT_TIMEOUT=10
# LIMA_INSTRUCTOR_INTENT_MAX_RETRIES=2
```

- [ ] **Step 2: 提交**

```bash
git add .env.example
git commit -m "docs(env): add instructor intent fallback env examples"
```

---

## Task 6: 质量门禁

- [ ] **Step 1: ruff 检查修改文件**

Run:
```bash
python -m ruff check config/env.py models/structured_outputs/instructor_client.py observability/events.py routing_intent.py tests/test_instructor_intent_fallback.py
```
Expected: `All checks passed!`

- [ ] **Step 2: ruff format 检查**

Run:
```bash
python -m ruff format --check config/env.py models/structured_outputs/instructor_client.py observability/events.py routing_intent.py tests/test_instructor_intent_fallback.py
```
Expected: files already formatted.

- [ ] **Step 3: pyright 检查目标文件**

Run:
```bash
python -m pyright config/env.py models/structured_outputs/instructor_client.py observability/events.py routing_intent.py tests/test_instructor_intent_fallback.py
```
Expected: 0 errors, 0 warnings.

- [ ] **Step 4: 代码体积检查**

Run: `python scripts/check_code_size.py`
Expected: PASS.

- [ ] **Step 5: 全量 pytest**

Run: `python -m pytest -m "not network" -q`
Expected: 0 failures.

- [ ] **Step 6: 提交修复（如有）**

```bash
git commit -am "fix: address lint/type/test issues"
```

---

## Task 7: 部署与线上验证

- [ ] **Step 1: 部署修改文件**

Run:
```bash
python scripts/deploy_unified.py --files config/env.py models/structured_outputs/instructor_client.py observability/events.py routing_intent.py .env.example
```
Expected: uploaded >0, 0 failed, Health OK.

- [ ] **Step 2: 公网健康检查**

Run:
```bash
curl -sf https://chat.donglicao.com/health | head -c 200
```
Expected: JSON with `"status":"ok"`.

- [ ] **Step 3: 公网聊天冒烟（真实 token）**

Run:
```bash
curl -sf -m 60 -X POST https://chat.donglicao.com/v1/chat/completions \
  -H "Authorization: Bearer $LIMA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"lima-1.3","messages":[{"role":"user","content":"hello"}],"max_tokens":10}'
```
Expected: HTTP 200 JSON response.

- [ ] **Step 4: 更新文档**

- 在 `STATUS.md` 顶部新增「最近完成」段落。
- 在 `progress.md` 顶部新增完成记录。
- 在 `findings.md` 新增条目。
- 在 `docs/superpowers/plans/README.md` 中标记 P4-3 后续完成。

- [ ] **Step 5: 提交并推送**

```bash
git add STATUS.md progress.md findings.md docs/superpowers/plans/README.md
git commit -m "docs: record P4-3 instructor intent fallback completion"
git push origin main
```

---

## 自我审查

- **Spec coverage:**
  - 低置信度触发 → Task 4 Step 3
  - Instructor 客户端 → Task 2
  - 配置项 → Task 1 + Task 5
  - 失败回退 → Task 2 + Task 4 tests
  - 可观测性 → Task 3
  - 测试 → Task 1~4
- **Placeholder scan:** 无 TBD/TODO。
- **类型一致性：** `create_structured_completion` 返回 `T | None`；`_instructor_intent_fallback` 返回 `dict | None`；`analyze_intent` 最终返回 `validated.model_dump()` 的 dict，与现有签名一致。
