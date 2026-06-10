# 请求管道权威文档 (REF-005)

日期: 2026-05-25 (扩展 CQ-087)

## 决策

生产环境的 LiMa 聊天请求使用**显式、分层的管道**。没有单一的
`factory.build_default_pipeline()` 拥有实时路径。

权威顺序：

1. **边缘** — `server.py`, `http_body_limit.BodySizeLimitMiddleware`, `access_guard`
2. **协议路由** — `routes/chat_endpoints.py`, `routes/anthropic_messages_handler.py`, `routes/tool_forward*.py`
3. **预检** — `routes/chat_preflight.py`, `server_context.py`, 可选 `context_pipeline.guardrails`
4. **路由** — `routing_engine.route()` (后端选择 + 执行的权威)
5. **HTTP 传输** — `http_caller` → `http_sync` / `http_async` / `http_stream`
6. **后处理** — `route_post_process.py`, `response_cleaner.py`, `identity_guard.py`
7. **关闭** — `routes/chat_post_closeout.py` (内存、可观测性、蒸馏队列)

`context_pipeline.factory.build_default_pipeline()` 仍然是**实验室/测试工具**
用于 IDE/场景/提示实验。生产环境仅在专注测试和 VPS 冒烟后采用部分组件 (检索统一模式, CQ-059)。

## 模块职责矩阵

| 关注点 | 权威模块 | 遗留/兼容外观 | 备注 |
|--------|----------|---------------|------|
| 后端注册 | `backends_registry.py` + `backends_constants.py` | `backends.py` 重导出 | 检测助手位于外观中 |
| 意图 + 层级分类 | `routing_classifier.py` | `smart_router.classify` | `classify()` → request_type; `classify_scenario()` → scenario |
| 后端池定义 | `router_v3.py` | — | `POOLS` 字典; `select_backends()` 按 request_type 返回候选 |
| 后端排名 | `routing_selector.py` | — | `select()`综合 health/budget/sticky/ML/memory/评分 |
| 后端执行 | `routing_executor.py` | — | `execute()`按序/并行尝试，记录 health 成功/失败 |
| HTTP 传输 | `http_caller.py` | `router_http.py` (urllib) | 将调用者迁移到 httpx 栈 |
| 健康/冷却 | `health_tracker.py` | `router_circuit_breaker.py` | 新代码优先使用 health_tracker |
| 预算管理 | `budget_manager.py` | — | `is_budget_available` + `record_usage` |
| 粘性会话 | `sticky_session.py` | — | `pin_backend` / `get_pinned_backend` |
| 路由评分 | `route_scorer.py` | — | 质量/稳定性/延迟/任务适配评分 |
| 流桥接 | `streaming.py`, `routes/stream_handlers.py` | `routes/anthropic_stream.py` | 工具原生 vs 模拟 SSE |
| 检索注入 | `context_pipeline/retrieval_injection.py` | `local_retrieval` | 知识图谱/向量检索 |
| 代码上下文注入 | `context_pipeline/code_context_injection.py` | — | tree-sitter 扫描 |
| 技能注入 | `skills_injector.py` | — | 温度门控 |
| 语义缓存 | `semantic_cache.py` | — | 仅 temperature=0 |
| 会话内存写入 | `session_memory/store*.py` | — | 拆分: db/crud/promote/admin |
| 质量重试 | `routes/quality_gate*.py` | 根 `quality_gate.py` (编码评估) | **不同模块** |
| 响应验证 | `context_pipeline/response_validator.py` | — | 编码响应质量检查 |
| 路由后钩子 | `route_post_process.py` | — | 关联/证据/反馈 |
| 代理任务 HTTP | `routes/agent_tasks.py` | store/service/schemas 子模块 | 不在聊天热路径上 |
| 代理运行队列 | `agent_runtime/orchestrator*.py` | `orchestrator.py` 外观 | 本地租赁队列 |
| 运维指标 | `routes/ops_metrics.py` | — | 读取 `app.state.stats` |

## routing_engine.route() 内部管线

`routing_engine.route()` 是唯一路由入口，内部按序执行：

```text
1. identity_guard    — 身份识别短路 (→ 直接返回)
2. semantic_cache    — 缓存命中短路 (→ 直接返回)
3. classify          — request_type (ide/chat/code/image)
4. classify_scenario — scenario (coding/chat/device/...)
5. skill_store       — 技能记忆召回 → recalled_backend
6. retrieval_injection — 知识图谱/向量上下文注入
7. code_context      — (coding only) tree-sitter 代码上下文
8. memory_promote    — (coding only) 历史 coding_fact/routing_lesson
9. complexity        — 请求复杂度评估
10. code_orchestrator — (coding + call_fn) 编码 tier 逻辑 (→ 短路返回)
11. router_v3.select_backends → routing_selector.select — 后端排名
12. skills_injector  — Skills 注入到 messages
13. context_compressor — (可选) 长对话压缩
14. speculative      — (简单请求) 推测性并行调用
15. routing_executor.execute — 按序/并行执行 + fallback
16. response_validator — (coding) 响应质量验证 + 重试
17. route_post_process — 后处理 (correlation/evidence/feedback)
18. feedback_bridge  — 闭环反馈记录
```

## 请求流程 (聊天)

```mermaid
sequenceDiagram
    participant Client
    participant Server as server.py
    participant Route as chat_endpoints
    participant Pre as chat_preflight
    participant RE as routing_engine
    participant HC as http_caller
    participant PP as route_post_process
    participant Close as chat_post_closeout

    Client->>Server: POST /v1/chat or /v1/messages
    Server->>Route: 认证 + 处理器
    Route->>Pre: 防护栏、预算、身份
    Pre->>RE: route(messages)
    RE->>HC: 调用后端
    HC-->>RE: 响应
    RE->>PP: 清理/品牌/工具
    PP->>Close: 内存 + 指标
    Close-->>Client: JSON 或 SSE
```

## 新生产代码不应使用的模块

| 模块 | 状态 |
|------|------|
| `smart_router.py` 聊天路径 | 遗留。保留 warmup/distill/ROUTE 兼容；新请求走 `routing_engine.route()` |
| `router_http.py` 直接调用 | 遗留 urllib 路径；使用 `http_caller` |
| `v3_integration.py` | 已废弃；被 `routing_engine` 取代 |
| `fallback_chain.py` | 未引用 |
| `context_pipeline.factory` 作为唯一管道 | 仅限实验室 |
| `deploy/key_rotation.py` | 已退役 (归档在 `scripts/archive/`) |

## 保护权威的测试

- `tests/test_routing_engine.py` — 层行为
- `tests/test_production_retrieval.py` — 实时路径上的检索
- `tests/test_route_post_process.py` — 路由后钩子
- `tests/test_http_caller.py` — 传输
- `tests/test_request_context_preflight.py` — 预检契约
- `tests/test_request_pipeline_authority.py` — 模块职责矩阵 (CQ-095)

## 何时重新审视完整工厂权威

- `server.py` 保持精简，所有路由模块仅通过 `route_registry` 注册
- 对等测试：工厂阶段 vs 生产跟踪 用于 `/v1/messages` 和 `/v1/chat/completions`
- CTX-003 预检需要一个可组合的管道，具有可测量的令牌预算

## 相关文档

- `docs/ROUTING_ENGINE_DESIGN.md`
- `docs/CODE_QUALITY_IMPROVEMENT_PLAN_2026-05-25.md`
- `docs/CONTEXT_PIPELINE.md` (实验室管道)