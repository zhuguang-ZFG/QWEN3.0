# P4-8 全链路追踪实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `context_pipeline/tracing.py` 接入生产聊天请求路径，使每次 `/v1/chat/completions` 生成可查询的完整 trace，并通过响应头和 `/admin/api/traces/recent` 暴露。

**Architecture:** 在 `routing_engine.route()` 内部 8+ 关键步骤包裹 `trace_span()` 上下文管理器；请求入口创建/复用 trace，响应头注入 `X-LiMa-Trace-Id`；`observability/metrics.py` 维护最近 1000 条 trace 的内存 ring buffer；新增 admin 路由供授权查询。

**Tech Stack:** Python 3.10、FastAPI、`context_pipeline/tracing.py`、pytest。

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `config/settings_core.py` | 新增 `LIMA_TRACING_ENABLED` 配置项 |
| `config/env.py` | 导出 `tracing_enabled()` 读取开关 |
| `routing_engine_trace.py` | 提供 `trace_span()` 上下文管理器与元数据辅助 |
| `observability/metrics.py` | 新增 `record_trace` / `get_recent_traces` / `reset_traces` ring buffer |
| `routing_engine_helpers.py` | `identity_shortcut` / `build_route_result` 插桩 |
| `routing_engine.py` | `classify` / `scenario` / `recall` / `retrieval` / `select` / `skills` 插桩 |
| `routing_engine_execute_strategy.py` | `execute` / `speculative` / `standard_execute` 插桩 |
| `routes/chat_response_finalize.py` | 非流式响应注入 `X-LiMa-Trace-Id` |
| `routes/chat_handler_dispatch.py` | 流式响应注入 `X-LiMa-Trace-Id` |
| `routes/chat_handler.py` | `_start_trace()` 支持复用外部传入的 trace |
| `routes/chat_endpoints.py` | 请求入口创建 trace、传递给下游、记录到 ring buffer |
| `routes/admin_traces.py` | 新增 `/admin/api/traces/recent` 查询端点 |
| `routes/admin.py` | include `admin_traces` 路由 |
| `context_pipeline/tracing.py` | 新增 `RequestTrace.finish()` 关闭所有 span 并导出 |
| `tests/test_routing_engine_trace.py` | `trace_span` 行为测试 |
| `tests/test_observability_trace_buffer.py` | ring buffer 测试 |
| `tests/test_admin_traces.py` | admin 端点测试 |
| `tests/test_chat_endpoints_trace_header.py` | 响应头测试 |

---

### Task 1: 增加 `LIMA_TRACING_ENABLED` 配置开关

**Files:**
- Modify: `config/settings_core.py:244-253`
- Modify: `config/env.py:35-54`（`__all__`）
- Modify: `config/env.py:220-221` 后新增函数
- Test: `tests/test_config_env.py`（如存在，否则新增断言在 `tests/test_routing_engine_trace.py`）

- [ ] **Step 1: 在 `ObservabilityConfig` 增加 `tracing_enabled`**

```python
# config/settings_core.py
    structured_logging: bool = os.environ.get("LIMA_STRUCTURED_LOGGING", "0").strip().lower() in {"1", "true", "yes"}
    service_name: str = os.environ.get("LIMA_SERVICE_NAME", "lima-router")
    tracing_enabled: bool = os.environ.get("LIMA_TRACING_ENABLED", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }
```

- [ ] **Step 2: 在 `config/env.py` 导出读取函数并加入 `__all__`**

```python
# config/env.py __all__ 增加
    "tracing_enabled",


def tracing_enabled() -> bool:
    """Whether request-level full-link tracing is enabled."""
    from config.settings import OBSERVABILITY

    return OBSERVABILITY.tracing_enabled
```

- [ ] **Step 3: 运行现有配置测试，确认无导入错误**

Run: `python -m pytest tests/test_config_env.py -v`（如无此文件则跳过）
Expected: PASS 或文件不存在

---

### Task 2: 新增 `routing_engine_trace.py` 上下文管理器

**Files:**
- Create: `routing_engine_trace.py`
- Test: `tests/test_routing_engine_trace.py`

- [ ] **Step 1: 编写失败测试**（`trace_span` 不存在）

```python
# tests/test_routing_engine_trace.py
import pytest

from context_pipeline.tracing import RequestTrace, new_trace


class TestTraceSpan:
    def test_trace_span_disabled_returns_none(self, monkeypatch):
        monkeypatch.setenv("LIMA_TRACING_ENABLED", "0")
        from routing_engine_trace import trace_span

        with trace_span("test") as span:
            assert span is None

    def test_trace_span_creates_and_ends_span(self, monkeypatch):
        monkeypatch.setenv("LIMA_TRACING_ENABLED", "1")
        from routing_engine_trace import trace_span

        trace = new_trace()
        with trace_span("step", request_type="chat") as span:
            assert span is not None
            assert span.name == "step"
            assert span.metadata["request_type"] == "chat"
        assert span.is_complete
        assert any(s.name == "step" for s in trace.spans)

    def test_trace_span_ends_on_exception(self, monkeypatch):
        monkeypatch.setenv("LIMA_TRACING_ENABLED", "1")
        from routing_engine_trace import trace_span

        trace = new_trace()
        with pytest.raises(ValueError):
            with trace_span("step") as span:
                assert span is not None
                raise ValueError("boom")
        assert trace.spans[0].is_complete
        assert trace.spans[0].metadata.get("error") == "ValueError"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_routing_engine_trace.py -v`
Expected: `ImportError: cannot import name 'trace_span' from 'routing_engine_trace'`

- [ ] **Step 3: 实现 `routing_engine_trace.py`**

```python
"""Trace span helpers for the routing engine."""

from __future__ import annotations

import contextlib
import logging
from typing import Generator

from context_pipeline.tracing import get_current_trace
from config.env import tracing_enabled

_log = logging.getLogger(__name__)


@contextlib.contextmanager
def trace_span(name: str, **metadata) -> Generator:
    """Start/end a span on the current trace. Yields None when tracing disabled."""
    if not tracing_enabled():
        yield None
        return

    trace = get_current_trace()
    if trace is None:
        yield None
        return

    span = trace.start_span(name, **metadata)
    try:
        yield span
    except Exception as exc:
        if span is not None:
            span.metadata["error"] = type(exc).__name__
            span.metadata["error_msg"] = str(exc)
        raise
    finally:
        trace.end_span(span)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_routing_engine_trace.py -v`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add config/settings_core.py config/env.py routing_engine_trace.py tests/test_routing_engine_trace.py
git commit -m "feat(tracing): add LIMA_TRACING_ENABLED and routing_engine_trace span helper"
```

---

### Task 3: `observability/metrics.py` 增加 trace ring buffer

**Files:**
- Modify: `observability/metrics.py:1-18`
- Modify: `observability/metrics.py:180-196`
- Test: `tests/test_observability_trace_buffer.py`

- [ ] **Step 1: 编写失败测试**

```python
# tests/test_observability_trace_buffer.py
from observability.metrics import get_recent_traces, record_trace, reset_metrics, reset_traces


class TestTraceBuffer:
    def test_record_and_get_recent_traces(self):
        reset_traces()
        record_trace({"trace_id": "t1"})
        record_trace({"trace_id": "t2"})
        recent = get_recent_traces(limit=10)
        assert [t["trace_id"] for t in recent] == ["t1", "t2"]

    def test_get_recent_traces_respects_limit(self):
        reset_traces()
        for i in range(5):
            record_trace({"trace_id": f"t{i}"})
        recent = get_recent_traces(limit=2)
        assert len(recent) == 2
        assert recent[-1]["trace_id"] == "t4"

    def test_reset_traces_clears_buffer(self):
        reset_traces()
        record_trace({"trace_id": "tx"})
        reset_traces()
        assert get_recent_traces(limit=10) == []

    def test_reset_metrics_clears_traces(self):
        reset_traces()
        record_trace({"trace_id": "ty"})
        reset_metrics()
        assert get_recent_traces(limit=10) == []
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_observability_trace_buffer.py -v`
Expected: `ImportError` 或 `NameError`

- [ ] **Step 3: 实现 ring buffer**

```python
# observability/metrics.py 顶部 imports 增加
from collections import defaultdict, deque

# observability/metrics.py 全局变量区增加
MAX_RECENT_TRACES = 1000
_recent_traces: deque[dict] = deque(maxlen=MAX_RECENT_TRACES)

# observability/metrics.py record() 函数不变，新增以下公开函数

def record_trace(trace_dict: dict) -> None:
    """Append a structured trace to the in-memory ring buffer."""
    with _lock:
        _recent_traces.append(trace_dict)


def get_recent_traces(limit: int = 100) -> list[dict]:
    """Return the most recent traces (oldest first)."""
    with _lock:
        return list(_recent_traces)[-limit:]


def reset_traces() -> None:
    """Clear trace ring buffer. For test isolation only."""
    with _lock:
        _recent_traces.clear()
```

并修改 `reset_metrics()`，在末尾加入 `reset_traces()` 调用，确保测试隔离。

```python
# reset_metrics() 末尾
        _session_backends.clear()
        reset_traces()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_observability_trace_buffer.py -v`
Expected: 4 passed

- [ ] **Step 5: 提交**

```bash
git add observability/metrics.py tests/test_observability_trace_buffer.py
git commit -m "feat(tracing): add in-memory trace ring buffer to metrics"
```

---

### Task 4: 在 `routing_engine_helpers.py` 插桩 identity / post_process

**Files:**
- Modify: `routing_engine_helpers.py`
- Test: `tests/test_routing_engine_helpers_trace.py`（新建，或合并到 `tests/test_routing_engine_trace.py`）

- [ ] **Step 1: 修改 `identity_shortcut`**

```python
# routing_engine_helpers.py imports 增加
from routing_engine_trace import trace_span


def identity_shortcut(query: str, channel_role: str, t0: float) -> RouteResult | None:
    """检测身份类问题并返回提前结果；无命中返回 None。"""
    with trace_span("identity", channel_role=channel_role):
        identity_answer = identity_guard.detect_identity_question(query, channel_role=channel_role)
        if identity_answer:
            ms = int((time.time() - t0) * 1000)
            return RouteResult(backend="identity_guard", answer=identity_answer, request_type="identity", ms=ms)
    return None
```

- [ ] **Step 2: 修改 `build_route_result`**

```python
def build_route_result(
    t0: float,
    picked: PickResult,
    final_backend: str,
    answer: str,
    messages: list[dict],
    injected_ids: list,
    backends: list[str],
    original_backend: str,
    fallback_used: bool,
) -> RouteResult:
    """构造最终 RouteResult 并计算耗时；先执行 post_route 上报。"""
    ms = int((time.time() - t0) * 1000)
    with trace_span(
        "post_process",
        final_backend=final_backend,
        fallback_used=fallback_used,
        request_type=picked.request_type,
        scenario=picked.scenario,
        ms=ms,
    ) as span:
        post_route(answer, final_backend, backends, picked.messages, messages, picked.request_type, picked.scenario, ms)
        if span is not None:
            span.metadata["ms"] = ms
    return RouteResult(
        backend=final_backend,
        answer=answer,
        request_type=picked.request_type,
        scenario=picked.scenario,
        ms=ms,
        fallback_used=fallback_used,
        skills_injected=injected_ids,
        retrieval_context=picked.retrieval_context,
    )
```

- [ ] **Step 3: 运行相关测试**

Run: `python -m pytest tests/test_routing_engine*.py -v`
Expected: 全部通过

- [ ] **Step 4: 提交**

```bash
git add routing_engine_helpers.py
git commit -m "feat(tracing): instrument identity shortcut and post_process span"
```

---

### Task 5: 在 `routing_engine.py` 插桩 classify / scenario / recall / retrieval / select / skills

**Files:**
- Modify: `routing_engine.py`
- Test: `tests/test_routing_engine_trace_spans.py`

- [ ] **Step 1: 修改 imports**

```python
# routing_engine.py imports 增加
from routing_engine_trace import trace_span
```

- [ ] **Step 2: 修改 `_classify_and_recall`**

```python
def _classify_and_recall(
    query: str,
    messages: list[dict],
    fmt: str,
    ide_source: str,
    system_prompt: str,
    headers: dict,
) -> tuple[str, str, str | None, str]:
    """Classify request type/scenario and recall backend + retrieval context."""
    with trace_span("classify") as span:
        req_type = classify(query, messages, fmt=fmt, ide_source=ide_source, system_prompt=system_prompt, headers=headers)
        if span is not None:
            span.metadata["request_type"] = req_type

    with trace_span("scenario") as span:
        scenario = classify_scenario(messages, query=query, ide_source=ide_source, request_type=req_type)
        if span is not None:
            span.metadata["scenario"] = scenario

    with trace_span("recall") as span:
        recall_attempt = try_recall_backend(messages, scenario)
        if span is not None:
            span.metadata["recalled_backend"] = recall_attempt

    with trace_span("retrieval") as span:
        messages, retrieval_text = inject_retrieval_context(messages)
        if span is not None:
            span.metadata["has_context"] = bool(retrieval_text)

    return req_type, scenario, recall_attempt, retrieval_text
```

- [ ] **Step 3: 修改 `_select_backends`**

```python
def _select_backends(
    req_type: str,
    scenario: str,
    recall_attempt: str | None,
    messages: list[dict],
    needs_tools: bool,
    preferred_backend: str,
    model: str,
) -> tuple[str, list[str]]:
    """Select backends based on health, sticky session, and recall."""
    with trace_span("select") as span:
        sticky_key = sticky_session.compute_key(model or "default", messages)
        hmap = health_tracker.get_health_map()
        backends = select(
            req_type,
            hmap,
            sticky_key=sticky_key,
            scenario=scenario,
            needs_tools=needs_tools,
            recalled_backend=recall_attempt,
            preferred_backend=preferred_backend or "",
        )
        if span is not None:
            span.metadata["backends"] = backends
        return sticky_key, backends
```

- [ ] **Step 4: 修改 `_enrich_with_intent_and_skills`**

```python
def _enrich_with_intent_and_skills(
    messages: list[dict],
    query: str,
    system_prompt: str,
    ide_source: str,
    backends: list[str],
) -> tuple[list[dict], str]:
    """Analyze intent (with optional semantic-router shortcut), inject skills, compress."""
    with trace_span("skills") as span:
        intent = resolve_intent(query, system_prompt, ide_source)
        route_role = intent if intent.startswith("device_") else ""
        prompt_scenario = intent_to_prompt_scenario(intent) or ""

        messages_out = inject_skills(
            messages,
            backend=backends[0] if backends else "",
            ide_source=ide_source,
            system_prompt=system_prompt,
            intent=intent,
            route_role=route_role,
            scenario=prompt_scenario,
        )
        messages_out = auto_compress(messages_out, backends, system_prompt)
        if span is not None:
            span.metadata["intent"] = intent
            span.metadata["scenario"] = prompt_scenario
        return messages_out, prompt_scenario
```

- [ ] **Step 5: 编写 span 数量测试**

```python
# tests/test_routing_engine_trace_spans.py
from unittest.mock import MagicMock, patch

from context_pipeline.tracing import new_trace
from routing_engine import route


def test_route_generates_at_least_eight_spans(monkeypatch):
    monkeypatch.setenv("LIMA_TRACING_ENABLED", "1")
    trace = new_trace()

    def fake_call_fn(backend, messages, max_tokens, tools=None):
        return f"answer-from-{backend}"

    with patch("routing_engine.classify", return_value="chat"), \
         patch("routing_engine.classify_scenario", return_value="general"), \
         patch("routing_engine.sticky_session.compute_key", return_value="key"), \
         patch("routing_engine.health_tracker.get_health_map", return_value={}), \
         patch("routing_engine.select", return_value=["longcat_chat"]), \
         patch("routing_engine.resolve_intent", return_value="chat"), \
         patch("routing_engine.inject_skills", side_effect=lambda messages, **kw: messages), \
         patch("routing_engine.auto_compress", side_effect=lambda msgs, *a, **kw: msgs), \
         patch("routing_engine.try_recall_backend", return_value=None), \
         patch("routing_engine.inject_retrieval_context", return_value=([], "")), \
         patch("routing_engine.lookup_cached_response", return_value=None), \
         patch("routing_engine.store_cached_response"):
        result = route(
            "hello",
            [{"role": "user", "content": "hello"}],
            call_fn=fake_call_fn,
            cache_enabled=True,
        )

    names = [s.name for s in trace.spans]
    required = {"classify", "scenario", "recall", "retrieval", "select", "skills", "post_process"}
    assert result.backend == "longcat_chat"
    assert required.issubset(set(names)), f"missing spans: {required - set(names)}, got {names}"
```

- [ ] **Step 6: 运行新增与现有测试**

Run: `python -m pytest tests/test_routing_engine_trace_spans.py tests/test_routing_engine*.py -v`
Expected: 全部通过

- [ ] **Step 7: 提交**

```bash
git add routing_engine.py tests/test_routing_engine_trace_spans.py
git commit -m "feat(tracing): instrument routing_engine classify/scenario/recall/retrieval/select/skills"
```

---

### Task 6: 在 `routing_engine_execute_strategy.py` 插桩 execute / speculative

**Files:**
- Modify: `routing_engine_execute_strategy.py`
- Test: `tests/test_routing_engine_execute_strategy_trace.py`（或合并）

- [ ] **Step 1: 修改 imports**

```python
# routing_engine_execute_strategy.py imports 增加
from routing_engine_trace import trace_span
```

- [ ] **Step 2: 修改 `execute_with_strategy`**

```python
def execute_with_strategy(
    call_fn: Callable,
    backends: list[str],
    messages: list[dict],
    max_tokens: int,
    query: str,
    req_type: str,
    scenario: str,
    needs_tools: bool,
    tools: list[dict] | None,
    sticky_key: str,
) -> tuple[str, str]:
    """根据复杂度选择执行策略（投机/标准），返回 (backend, answer)。"""
    complexity = speculative.classify_complexity(query, messages)

    with trace_span("execute", strategy="unknown") as span:
        if needs_tools:
            final_backend, answer = _run_standard_execute(
                backends, call_fn, messages, max_tokens, scenario, req_type, tools=tools
            )
        elif complexity == "simple" and req_type in ("ide", "chat"):
            final_backend, answer = _try_speculative(backends, call_fn, messages, max_tokens, scenario, req_type)
        else:
            final_backend, answer = _run_standard_execute(
                backends, call_fn, messages, max_tokens, scenario, req_type
            )

        if final_backend != "exhausted":
            sticky_session.pin_backend(sticky_key, final_backend)

        if span is not None:
            span.metadata["strategy"] = "speculative" if complexity == "simple" and req_type in ("ide", "chat") else "standard"
            span.metadata["final_backend"] = final_backend
        return final_backend, answer
```

- [ ] **Step 3: 修改 `_try_speculative`（可选，增加子 span）**

```python
def _try_speculative(
    backends: list[str],
    call_fn: Callable,
    messages: list[dict],
    max_tokens: int,
    scenario: str,
    req_type: str,
) -> tuple[str, str]:
    """尝试投机执行，回退到标准执行。"""
    affinity_backends = speculative.get_affinity_backends("simple")
    spec_candidates = [
        b
        for b in affinity_backends
        if not health_tracker.is_cooled_down(b)
        and budget_manager.is_budget_available(b)
        and speculative.is_historically_fast(b)
    ]
    if len(spec_candidates) >= 2:
        with trace_span("speculative", strategy="speculative") as span:
            try:
                final_backend, answer = speculative.speculative_call(
                    spec_candidates,
                    call_fn,
                    messages,
                    max_tokens,
                    max_parallel=5,
                    timeout_sec=5.0,
                    scenario=scenario,
                    request_type=req_type,
                )[:2]
                if span is not None:
                    span.metadata["final_backend"] = final_backend
                return final_backend, answer
            except RuntimeError:
                pass
    return _run_standard_execute(backends, call_fn, messages, max_tokens, scenario, req_type)
```

- [ ] **Step 4: 运行测试**

Run: `python -m pytest tests/test_routing_engine*.py -v`
Expected: 全部通过

- [ ] **Step 5: 提交**

```bash
git add routing_engine_execute_strategy.py
git commit -m "feat(tracing): instrument execute strategy and speculative span"
```

---

### Task 7: `context_pipeline/tracing.py` 新增 `RequestTrace.finish()`

**Files:**
- Modify: `context_pipeline/tracing.py`
- Test: `tests/test_tracing.py`

- [ ] **Step 1: 新增测试**

```python
# tests/test_tracing.py
class TestRequestTrace:
    # ... 已有测试 ...

    def test_finish_ends_all_spans_and_exports(self):
        trace = RequestTrace()
        trace.start_span("s1")
        trace.start_span("s2")
        result = trace.finish()
        assert all(s.is_complete for s in trace.spans)
        assert result["trace_id"] == trace.trace_id
        assert result["span_count"] == 2
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_tracing.py::TestRequestTrace::test_finish_ends_all_spans_and_exports -v`
Expected: `AttributeError: 'RequestTrace' object has no attribute 'finish'`

- [ ] **Step 3: 实现 `finish()`**

```python
# context_pipeline/tracing.py 在 RequestTrace 类中增加
    def finish(self) -> dict:
        """End all active spans and export the trace."""
        while self._active_span is not None:
            self.end_span()
        return self.export()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_tracing.py -v`
Expected: 全部通过

- [ ] **Step 5: 提交**

```bash
git add context_pipeline/tracing.py tests/test_tracing.py
git commit -m "feat(tracing): add RequestTrace.finish() to close all spans"
```

---

### Task 8: 非流式响应注入 `X-LiMa-Trace-Id`

**Files:**
- Modify: `routes/chat_response_finalize.py`

- [ ] **Step 1: 修改 imports 与 `finalize_success_response`**

```python
# routes/chat_response_finalize.py imports 增加
from context_pipeline.tracing import get_current_trace


async def finalize_success_response(
    ctx: ChatRunContext,
    req: ChatRequest,
    result: dict,
    intent: dict,
    *,
    model_id: str,
    record_request: RecordRequestFunc,
) -> JSONResponse:
    raw_answer = result.get("answer", "")
    content = clean_response(raw_answer, result.get("backend", "")) or raw_answer
    backend = result.get("backend", "unknown")
    intent_name = intent.get("intent", "unknown")
    duration_ms = int((time.time() - ctx.t0) * 1000)
    raw_total_ms = result.get("total_ms")
    total_ms = duration_ms if raw_total_ms is None else raw_total_ms

    _fire_side_effects(ctx, req, content, backend, intent_name, duration_ms, record_request, result)

    if ctx.fmt == "anthropic":
        response = JSONResponse(build_anthropic_response(ctx.chat_id, content, backend, ctx.request_model or model_id))
    else:
        response = JSONResponse(
            attach_memory_recall_meta(
                build_response(ctx.chat_id, content, backend, total_ms),
                ctx.memory_recall_meta,
            )
        )

    trace = get_current_trace()
    if trace is not None:
        response.headers["X-LiMa-Trace-Id"] = trace.trace_id
    return response
```

- [ ] **Step 2: 运行相关测试**

Run: `python -m pytest tests/test_routes_chat_handler.py tests/test_chat_handler.py -v`
Expected: 全部通过

- [ ] **Step 3: 提交**

```bash
git add routes/chat_response_finalize.py
git commit -m "feat(tracing): add X-LiMa-Trace-Id header to non-stream responses"
```

---

### Task 9: 流式响应注入 `X-LiMa-Trace-Id`

**Files:**
- Modify: `routes/chat_handler_dispatch.py`

- [ ] **Step 1: 修改 `build_streaming_response`**

```python
# routes/chat_handler_dispatch.py imports 增加
from context_pipeline.tracing import get_current_trace


def build_streaming_response(ctx: ChatRunContext, req: ChatRequest) -> StreamingResponse:
    routing_intent.analyze_intent(ctx.query, system_prompt=ctx.sys_prompt_preview, ide=ctx.ide_source)
    _chat_handler()  # ensures chat_handler deps are imported/injected
    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    trace = get_current_trace()
    if trace is not None:
        headers["X-LiMa-Trace-Id"] = trace.trace_id
    return StreamingResponse(
        stream_response(
            ctx.chat_id,
            ctx.query,
            False,
            ide_source=ctx.ide_source,
            sys_prompt_preview=ctx.sys_prompt_preview,
            use_thinking=ctx.prefs.use_thinking,
            messages=ctx.preflight.prompt_context_messages,
            prefer=ctx.prefs.prefer,
        ),
        media_type="text/event-stream",
        headers=headers,
    )
```

- [ ] **Step 2: 运行相关测试**

Run: `python -m pytest tests/test_routes_chat_handler.py -k stream -v`
Expected: 全部通过

- [ ] **Step 3: 提交**

```bash
git add routes/chat_handler_dispatch.py
git commit -m "feat(tracing): add X-LiMa-Trace-Id header to streaming responses"
```

---

### Task 10: 请求入口统一创建 trace 并记录到 ring buffer

**Files:**
- Modify: `routes/chat_handler.py`
- Modify: `routes/chat_endpoints.py`
- Test: `tests/test_chat_endpoints_trace_header.py`

- [ ] **Step 1: 修改 `routes/chat_handler._start_trace` 支持复用已有 trace**

```python
# routes/chat_handler.py imports 增加
from context_pipeline.tracing import get_current_trace, new_trace


def _start_trace(ide_source: str) -> Trace | None:
    try:
        existing = get_current_trace()
        if existing is not None:
            existing.start_span("handle_chat", ide=ide_source)
            return existing
        trace = new_trace()
        trace.start_span("handle_chat", ide=ide_source)
        return trace
    except ImportError as exc:
        _log.warning("context_pipeline.tracing unavailable: %s", exc)
        return None
```

- [ ] **Step 2: 修改 `routes/chat_endpoints.py` 请求入口**

```python
# routes/chat_endpoints.py imports 增加
from context_pipeline.tracing import get_current_trace, new_trace
from observability.metrics import record_trace


async def chat_completions(request: Request):
    """OpenAI-compatible chat completions endpoint."""
    body = await _read_json_body(request)
    if isinstance(body, JSONResponse):
        return body
    raw_messages = body.get("messages", [])
    client_ip = _call("client_ip", request)
    ide_source = _call("detect_ide", raw_messages)

    rate_limit_response = _check_rate_limit(client_ip, ide_source)
    if rate_limit_response is not None:
        return rate_limit_response

    sys_prompt_preview = extract_system_preview(raw_messages)

    # Create the request-level trace once per successful request.
    new_trace()

    vision_resp = await _handle_vision_shortcut(
        raw_messages,
        body,
        ide_source,
        client_ip,
        sys_prompt_preview,
    )
    if vision_resp is not None:
        _attach_trace_header_and_record(vision_resp)
        return vision_resp

    if body.get("tools"):
        _log.info("Tool call request routed through standard chat pipeline (native forwarding removed)")

    chat_req = _build_chat_request(body)
    if isinstance(chat_req, JSONResponse):
        return chat_req

    response = await maybe_await(
        _dep("handle_chat")(
            chat_req,
            fmt="openai",
            client_ip=client_ip,
            ide_source=ide_source,
            sys_prompt_preview=sys_prompt_preview,
            request_headers=dict(request.headers),
        )
    )
    _attach_trace_header_and_record(response)
    return response


def _attach_trace_header_and_record(response) -> None:
    trace = get_current_trace()
    if trace is None:
        return
    if not response.headers.get("X-LiMa-Trace-Id"):
        response.headers["X-LiMa-Trace-Id"] = trace.trace_id
    try:
        record_trace(trace.finish())
    except Exception as exc:
        _log.warning("record_trace failed: %s", exc, exc_info=True)
```

- [ ] **Step 3: 编写响应头测试**

```python
# tests/test_chat_endpoints_trace_header.py
from fastapi.testclient import TestClient

import routes.chat_endpoints as chat_endpoints
import server


def test_chat_completions_includes_trace_header(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-key")
    monkeypatch.setenv("LIMA_TRACING_ENABLED", "1")

    async def fake_handle_chat(req, **kwargs):
        from fastapi.responses import JSONResponse
        return JSONResponse({"ok": True})

    monkeypatch.setattr(server, "_handle_chat", fake_handle_chat)

    client = TestClient(server.app)
    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer test-key"},
        json={"model": "lima-1.3", "messages": [{"role": "user", "content": "hello"}]},
    )
    assert response.status_code == 200
    assert "X-LiMa-Trace-Id" in response.headers
    assert len(response.headers["X-LiMa-Trace-Id"]) == 12
```

- [ ] **Step 4: 运行新增与现有测试**

Run: `python -m pytest tests/test_chat_endpoints_trace_header.py tests/test_chat_endpoints.py -v`
Expected: 全部通过

- [ ] **Step 5: 提交**

```bash
git add routes/chat_handler.py routes/chat_endpoints.py tests/test_chat_endpoints_trace_header.py
git commit -m "feat(tracing): create trace at chat entry and record to ring buffer"
```

---

### Task 11: 新增 `/admin/api/traces/recent` 查询端点

**Files:**
- Create: `routes/admin_traces.py`
- Modify: `routes/admin.py`
- Test: `tests/test_admin_traces.py`

- [ ] **Step 1: 创建 `routes/admin_traces.py`**

```python
"""Admin trace inspection endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from observability.metrics import get_recent_traces
from routes.admin_auth import verify_admin

router = APIRouter()


@router.get("/api/traces/recent", dependencies=[Depends(verify_admin)])
async def admin_recent_traces(limit: int = Query(50, ge=1, le=1000)) -> dict:
    """Return the most recent request traces from the in-memory ring buffer."""
    return {"traces": get_recent_traces(limit)}
```

- [ ] **Step 2: 在 `routes/admin.py` include 路由**

```python
# routes/admin.py imports 增加
from routes.admin_traces import router as admin_traces_router

# router.include_router(admin_api_extra_router) 后增加
router.include_router(admin_traces_router)
```

- [ ] **Step 3: 编写 admin 测试**

```python
# tests/test_admin_traces.py
from fastapi import FastAPI
from fastapi.testclient import TestClient

from observability.metrics import record_trace, reset_traces
from routes import admin_traces
from routes.admin_auth import verify_admin


def test_admin_recent_traces_returns_recorded_traces(monkeypatch):
    monkeypatch.setenv("LIMA_ADMIN_TOKEN", "admin-secret")
    reset_traces()
    record_trace({"trace_id": "abc123", "spans": []})

    app = FastAPI()
    app.dependency_overrides[verify_admin] = lambda: None
    app.include_router(admin_traces.router, prefix="/admin")

    client = TestClient(app)
    response = client.get("/admin/api/traces/recent?limit=10")
    assert response.status_code == 200
    body = response.json()
    assert len(body["traces"]) == 1
    assert body["traces"][0]["trace_id"] == "abc123"
```

- [ ] **Step 4: 运行测试**

Run: `python -m pytest tests/test_admin_traces.py -v`
Expected: 1 passed

- [ ] **Step 5: 提交**

```bash
git add routes/admin_traces.py routes/admin.py tests/test_admin_traces.py
git commit -m "feat(tracing): add /admin/api/traces/recent endpoint"
```

---

### Task 12: 聚焦测试 → 全量测试 → 代码检查

- [ ] **Step 1: 聚焦测试**

Run: `python -m pytest tests/test_routing_engine_trace.py tests/test_observability_trace_buffer.py tests/test_routing_engine_trace_spans.py tests/test_tracing.py tests/test_chat_endpoints_trace_header.py tests/test_admin_traces.py -v`
Expected: 全部通过

- [ ] **Step 2: 全量 pytest**

Run: `python -m pytest -m "not network" -q`
Expected: 0 failed（允许已有的 flaky 单独重跑通过）

- [ ] **Step 3: ruff 检查**

Run: `ruff check .`
Expected: 0 errors

- [ ] **Step 4: pyright 检查修改文件**

Run: `pyright routing_engine.py routing_engine_helpers.py routing_engine_execute_strategy.py routing_engine_trace.py routes/chat_endpoints.py routes/chat_handler.py routes/chat_response_finalize.py routes/chat_handler_dispatch.py routes/admin_traces.py observability/metrics.py context_pipeline/tracing.py`
Expected: 无新增 error（允许可选依赖如 openai/instructor 的 warning）

- [ ] **Step 5: 代码体积检查**

Run: `python scripts/check_code_size.py`
Expected: 无新增超过 300 行文件 / 50 行函数

- [ ] **Step 6: 提交**

```bash
git commit -m "test(tracing): add focused and full test coverage for full-link tracing"
```

---

### Task 13: 文档同步与部署验证

- [ ] **Step 1: 更新 `STATUS.md` / `progress.md` / `findings.md`**

在 `progress.md` 追加一条：

```markdown
## 2026-06-27 P4-8 全链路追踪
- 实现 `routing_engine_trace.trace_span()` 与 `RequestTrace.finish()`
- 生产路径生成 8+ span（identity/classify/scenario/recall/retrieval/select/skills/execute/post_process）
- 响应头注入 `X-LiMa-Trace-Id`，ring buffer 支持 `/admin/api/traces/recent`
- 测试：新增 4 个测试文件，全量 pytest 0 failed
- 部署：`scripts/deploy_unified.py` 已执行，公网 `/v1/chat/completions` 返回 trace header
```

- [ ] **Step 2: 本地冒烟**

Run: `python -m uvicorn server:app --host 127.0.0.1 --port 8080 &`
Run: `curl -sf http://127.0.0.1:8080/health`
Expected: 200 OK

- [ ] **Step 3: 部署到 VPS**

Run: `python scripts/deploy_unified.py`
Expected: 成功上传、重启、健康检查通过

- [ ] **Step 4: 公网验证 trace header**

Run:
```bash
curl -s -D - https://chat.donglicao.com/v1/chat/completions \
  -H "Authorization: Bearer $LIMA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"lima-1.3","messages":[{"role":"user","content":"hi"}]}' \
  -o /tmp/chat_resp.json
```
Expected: 响应头包含 `X-LiMa-Trace-Id`

- [ ] **Step 5: 验证 admin 端点**

Run:
```bash
curl -s "https://chat.donglicao.com/admin/api/traces/recent?limit=5" \
  -H "Authorization: Bearer $LIMA_ADMIN_TOKEN"
```
Expected: JSON 返回最近 traces

- [ ] **Step 6: 提交文档更新**

```bash
git add STATUS.md progress.md findings.md
git commit -m "docs(tracing): record P4-8 full-link tracing deployment evidence"
```

---

## Self-Review

**1. Spec coverage:**

| 设计需求 | 实现任务 |
|----------|----------|
| 每次 `/v1/chat/completions` 生成 trace_id | Task 10 (`new_trace()` at entry) |
| 响应头 `X-LiMa-Trace-Id` | Task 8, Task 9, Task 10 |
| routing_engine.route() ≥8 spans | Task 4, Task 5, Task 6, Task 7 |
| `/admin/api/traces/recent` | Task 11 |
| 结构化日志包含 trace_id | 已有 `observability/structured_logging.py` 自动生效 |
| ≥5 个测试 | Task 2, 3, 5, 7, 10, 11 共 6 组测试 |
| pytest / ruff / pyright / check_code_size | Task 12 |
| 部署后公网冒烟 | Task 13 |

**2. Placeholder scan:** 无 `TBD`、`TODO`、无步骤缺失代码。

**3. Type consistency：**
- `trace_span(name: str, **metadata)` 全程一致。
- `RequestTrace.finish()` 返回 `dict` 与 `record_trace(trace_dict: dict)` 匹配。
- admin 端点路径 `/api/traces/recent` 与 `routes/admin.py` prefix `/admin` 组合后得到 `/admin/api/traces/recent`。

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-06-27-full-link-tracing-plan.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints for review.

**Which approach?**
