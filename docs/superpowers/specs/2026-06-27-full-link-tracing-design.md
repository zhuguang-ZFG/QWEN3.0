# P4-8 全链路追踪设计

> 状态：设计文档待审阅
> 相关计划：`docs/superpowers/plans/LiMa_QWEN3_系统增强细化方案_v3_20260624.md` 步骤 P4-8
> 作者：Kimi Code
> 日期：2026-06-27

## 1. 背景

P4-6 已完成管线状态可视化基座（`pipeline_graph.py` + `docs/assets/routing_pipeline.mmd`），但当前生产路径尚未对每次请求生成可查询的链路追踪。

`context_pipeline/tracing.py` 已提供轻量级 `RequestTrace` / `Span` 实现：

- 每个请求生成唯一 `trace_id`
- 支持嵌套 span（parent-child）
- 通过 `contextvars` 在当前上下文存取
- 可导出为结构化 dict

本设计将这套机制接入生产聊天请求路径，实现 P4-8 要求的“每步输入/输出/耗时可查”。

## 2. 目标

- 每次 `/v1/chat/completions` 请求生成一条完整 trace。
- 覆盖 `routing_engine.route()` 内部 12 个关键步骤：identity / classify / scenario / recall / retrieval / code_context / select / skills / speculative / execute / validate / post_process。
- 每个 span 记录耗时与关键元数据（如 request_type、backend、fallback_used）。
- trace_id 写入响应头 `X-LiMa-Trace-Id` 与结构化日志，便于排障。
- 最近 N 条 trace 保留在内存 ring buffer，提供 `/admin/api/traces/recent` 查询端点。
- 默认开启；开销目标 < 2%（单次 span 创建/结束 < 0.1ms）。

## 3. 方案对比

| 方案 | 依赖 | 优点 | 缺点 | 推荐度 |
|------|------|------|------|--------|
| A. 复用现有 `context_pipeline.tracing` | 无 | 零新增依赖；与现有日志/指标体系天然集成；实现快 | 功能较基础，无分布式跨服务传播 | **推荐** |
| B. 接入 OpenTelemetry SDK | `opentelemetry-api/sdk` | 生态成熟，可导出到多种后端 | 引入新依赖，配置复杂，对当前项目过重 | 不推荐 |
| C. 接入 LangSmith | `langsmith` | LLM-native 追踪 UI | 强依赖外部 SaaS，成本高，与 LiMa 自托管策略不符 | 不推荐 |

## 4. 推荐方案 A 详细设计

### 4.1 组件

- `context_pipeline/tracing.py`（已存在）：RequestTrace / Span / contextvars。
- **新增 `routing_engine_trace.py`**：提供 `trace_span(name, **metadata)` 上下文管理器，自动 start/end span 并处理异常。
- **修改 `routing_engine.py` / `routing_engine_helpers.py` / `routing_engine_execute_strategy.py` / `route_post_process.py`**：在关键步骤包裹 `trace_span(...)`。
- **修改 `routes/chat_endpoints.py`（或 `routes/chat_handler_dispatch.py`）**：请求入口创建 trace、响应头注入 trace_id、请求结束导出 trace 到 ring buffer。
- **新增 `routes/admin_traces.py`**：`GET /admin/api/traces/recent` 返回最近 traces（需 admin token）。
- **修改 `observability/metrics.py`**：新增 ring buffer `recent_traces: deque[dict]` 与 `record_trace(trace: dict)`。

### 4.2 数据流

```text
Client → server.py → routes/chat_endpoints.py
            │
            ├─ new_trace() → trace_id
            │
            ▼
      routing_engine.route()
            │
            ├─ trace_span("identity") ...
            ├─ trace_span("classify", request_type=...)
            ├─ trace_span("select", backends=[...])
            ├─ trace_span("execute", final_backend=...)
            └─ trace_span("post_process")
            │
            ▼
      response → headers["X-LiMa-Trace-Id"] = trace_id
            │
            ▼
      record_trace(trace.export()) → ring buffer
```

### 4.3 `routing_engine_trace.py` 接口

```python
from contextlib import contextmanager
from context_pipeline.tracing import get_current_trace

@contextmanager
def trace_span(name: str, **metadata):
    trace = get_current_trace()
    if trace is None:
        yield None
        return
    span = trace.start_span(name, **metadata)
    try:
        yield span
    finally:
        trace.end_span(span)
```

### 4.4 需要 instrument 的位置

| 步骤 | 位置 | 元数据 |
|------|------|--------|
| identity | `routing_engine_helpers.identity_shortcut` | channel_role |
| classify | `routing_engine._pick_for_route` | request_type |
| scenario | `routing_engine._pick_for_route` | scenario |
| recall | `routing_engine._classify_and_recall` | recalled_backend |
| retrieval | `routing_engine._classify_and_recall` | has_context |
| select | `routing_engine._select_backends` | backends |
| skills | `routing_engine._enrich_with_intent_and_skills` | injected_ids |
| speculative | `routing_engine_execute_strategy.execute_with_strategy` | strategy |
| execute | `routing_engine_execute_strategy.execute_with_strategy` | final_backend |
| validate | response_validator（如启用） | — |
| post_process | `routing_engine_helpers.build_route_result` | ms, fallback_used |

### 4.5 Ring Buffer 与 Admin 端点

- `observability/metrics.py` 新增：
  - `_recent_traces: deque[dict] = deque(maxlen=1000)`
  - `record_trace(trace_dict: dict) -> None`
  - `get_recent_traces(limit: int = 100) -> list[dict]`

- `routes/admin_traces.py`：
  - `GET /admin/api/traces/recent?limit=50` 返回最近 traces。
  - 复用现有 `access_guard` admin token 校验。

### 4.6 响应头

在 `routes/chat_endpoints.py` 的响应中注入：

```python
if trace := get_current_trace():
    response.headers["X-LiMa-Trace-Id"] = trace.trace_id
```

### 4.7 配置

无需新增环境变量；默认使用现有 tracing。若需关闭，可通过 `LIMA_TRACING_ENABLED=0`（可选，默认开启）。

## 5. 验收标准

- [ ] 每次 `/v1/chat/completions` 请求生成唯一 `trace_id`。
- [ ] 响应头包含 `X-LiMa-Trace-Id`。
- [ ] `routing_engine.route()` 至少生成 8 个 span（identity/classify/scenario/recall/select/skills/execute/post_process）。
- [ ] `/admin/api/traces/recent` 可查询最近 trace。
- [ ] 结构化日志包含 `trace_id`。
- [ ] 新增 ≥5 个测试覆盖 trace 创建、span 数量、响应头、ring buffer、admin 端点。
- [ ] 聚焦测试 + 全量 pytest 通过；`ruff` / `pyright` / `check_code_size` 通过。
- [ ] 部署后公网冒烟返回 `X-LiMa-Trace-Id`。

## 6. 风险与缓解

| 风险 | 缓解 |
|------|------|
| Span 增加请求延迟 | 仅记录耗时与轻量元数据；无序列化/网络 I/O；默认开启 |
| Ring buffer 占内存 | `maxlen=1000`，每条 trace 仅数 KB |
| 异常时 span 未结束 | `trace_span` 上下文管理器 `finally` 保证 end_span |
| Admin 端点泄露 trace | 复用 admin token 认证；trace 中不包含 prompt/key |
