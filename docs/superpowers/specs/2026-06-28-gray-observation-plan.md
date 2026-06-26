# P4-后续：灰度观测计划（Instructor 意图回退 + 语义缓存）

> 状态：🚧 计划中
> 作者：Kimi Code CLI
> 日期：2026-06-28
> 关联：`docs/superpowers/plans/README.md` 推荐下一步第 3 条；`STATUS.md` 2026-06-27 P4-8 完成记录

---

## 1. 目标与范围

在灰度环境开启并观测以下两项 P4 后续能力：

1. **Instructor 结构化意图回退**（P4-3 后续）
   - 开关：`LIMA_INSTRUCTOR_INTENT_ENABLED`
   - 当前位置：`routing_intent_instructor.py`
2. **语义缓存**（P4-5 后续）
   - 开关：`LIMA_SEMANTIC_CACHE_ENABLED`
   - 当前位置：`semantic_cache/`、`routing_engine_cache.py`

通过新增指标、Trace 语义 enrichment、Admin 端点，把「命中率、意图准确率、延迟」变成可查询的数据，再决定是否在主流程默认开启。

**不在本切片内**：多租户限流、LangGraph 状态机迁移、默认开启这两个开关。

---

## 2. 推荐方向理由

- `docs/superpowers/plans/README.md` 第 73 行明确把灰度观测列为推荐下一步。
- 前置条件已就绪：
  - P4-3 后续 `routing_intent_instructor.py` 已接入 `routing_intent.py` 生产路径。
  - P4-5 后续 `routing_engine_cache.py` 已接入 `routing_engine.py` 生产路径。
  - P4-8 全链路追踪已上线，可提供 `X-LiMa-Trace-Id` 与 `/admin/api/traces/recent`。
- 风险最低：默认关闭 → 灰度开启 → 收集指标 → 决策，不引入新架构依赖。
- 输出可为 P4-6 后续、P5/P6 提供真实数据输入。

---

## 3. 前置条件

| 前置 | 状态 | 文件 |
|------|------|------|
| Instructor 意图回退实现 | ✅ 已落地 | `routing_intent_instructor.py` |
| 语义缓存实现 | ✅ 已落地 | `semantic_cache/cache.py`、`routing_engine_cache.py` |
| 全链路追踪 | ✅ 已落地 | `context_pipeline/tracing.py`、`routing_engine_trace.py` |
| 环境变量定义 | ✅ 已存在 | `.env.example` 第 77–98 行、`config/env.py` 第 186–227 行 |

---

## 4. 总体架构

```text
Client → /v1/chat/completions
    → routing_engine.py
        ├─ trace_span("classify") / trace_span("cache_lookup")
        ├─ routing_intent_instructor.maybe_instructor_intent() ──► observability.metrics.record()
        ├─ routing_engine_cache.lookup_cached_response() ───────► observability.metrics.record()
        └─ routing_engine_cache.store_cached_response() ────────► observability.metrics.record()
    → routes/chat_endpoints.py
        ├─ response.headers["X-LiMa-Trace-Id"]
        └─ record_trace(trace.finish())
Admin  → /admin/api/metrics/gray       (新增)
Admin  → /admin/api/traces/recent      (已有，Trace  enriched)
```

---

## 5. Phase 0：文档发现（已完成）

### 5.1 已查阅的源

| 文件 | 关键章节 | 发现 |
|------|----------|------|
| `docs/superpowers/plans/README.md` | 第 69–73 行 | 明确推荐灰度观测 |
| `.env.example` | 第 77–98 行 | 已有 `LIMA_INSTRUCTOR_INTENT_ENABLED`、`LIMA_SEMANTIC_CACHE_ENABLED` 等开关 |
| `config/env.py` | 第 186–227 行 | 读取函数已存在 |
| `routing_intent_instructor.py` | 全文 | 失败/成功均已调用 `_record_metric(...)` |
| `routing_engine_cache.py` | 全文 | lookup/store 尚未记录命中/失败指标 |
| `observability/events.py` | 第 223–233 行 | `instructor_intent_event()` 已定义 |
| `observability/metrics.py` | 第 17–42、57–96 行 | 已有计数器/采样器模式 |
| `routes/admin_traces.py` | 全文 | Admin 端点模式：依赖 `verify_admin` |
| `routes/ops_metrics/collectors.py` | 第 245–283 行 | Ops 快照目前从 `app.state.stats` 取数，未消费 `observability.metrics` |

### 5.2 Allowed APIs（本计划将使用的接口）

- `observability.metrics.record(event: LiMaEvent)` — 已有事件入口。
- `observability.events.LiMaEvent` / 事件工厂函数 — 已有模式。
- `observability.metrics.get_metrics_snapshot()` — 将扩展返回 gray 子树。
- `context_pipeline.tracing.trace_span()` / `Span.metadata` — P4-8 已落地。
- `routes.admin_auth.verify_admin` — Admin 认证依赖。

### 5.3 必须避开的反模式

- 不允许 `except Exception: pass`（AGENTS.md 硬规则）。
- 不允许在核心路径新增同步网络调用。
- 不允许把原始 query/response 写入指标（已脱敏）。
- 不允许让灰度开关缺失时抛出启动错误（必须安全默认关闭）。

---

## 6. Phase 1：指标暴露

### 6.1 做什么

1. **扩展 `observability/metrics.py`**
   - 新增灰度计数器（线程安全，与现有 `_lock` 同锁）：
     - `_semantic_cache_hit`、`semantic_cache_miss`、`semantic_cache_skip`、`semantic_cache_error`
     - `_instructor_intent_success`、`_instructor_intent_failure`、`_instructor_intent_skip`
   - 新增延迟采样：
     - `_instructor_intent_latency_samples`（max 200，复用 `_percentile`）
   - 在 `record(event)` 分支中识别新事件类型并聚合。
   - 在 `get_metrics_snapshot()` 返回中新增 `"gray_observation"` 字段，包含：
     - `semantic_cache.hit_rate` = hit / (hit + miss)
     - `semantic_cache.avg_lookup_ms`、`p95_lookup_ms`
     - `instructor_intent.success_rate`
     - `instructor_intent.avg_latency_ms`、`p95_latency_ms`
     - 各项原始计数
2. **让 `routing_engine_cache.py` 发出事件**
   - `lookup_cached_response()` 在命中/未命中/异常时分别发出 `semantic_cache_hit` / `semantic_cache_miss` / `semantic_cache_error` 事件。
   - `store_cached_response()` 在成功写入时发出 `semantic_cache_store` 事件（仅计数，不阻塞）。
   - 参考 `routing_intent_instructor.py` 中 `_record_metric(instructor_intent_event(...))` 的写法。
3. **扩展 `observability/events.py`**
   - 新增工厂函数：
     - `semantic_cache_event(kind: str, latency_ms: float = 0.0, similarity: float = -1.0) -> LiMaEvent`
     - `instructor_intent_latency_event(provider, model, latency_ms) -> LiMaEvent`
   - 事件类型字符串使用小写 + 下划线，如 `"semantic_cache_hit"`。
4. **让 `routing_intent_instructor.py` 记录延迟**
   - 在 `maybe_instructor_intent()` 内用 `time.time()` 计算耗时，成功后发出 `instructor_intent_latency_event`。
5. **新增 Admin 端点 `routes/admin_metrics.py`**
   - `GET /admin/api/metrics/gray`，依赖 `verify_admin`。
   - 返回 `observability.metrics.get_metrics_snapshot()["gray_observation"]`。
   - 注册到 `routes/route_registry.py`（参考 `routes/admin_traces.py` 的注册方式）。

### 6.2 参考代码位置

- 计数器模式：`observability/metrics.py` 第 19–34 行。
- `record()` 分支模式：第 57–96 行。
- 事件工厂模式：`observability/events.py` 第 67–172 行。
- Admin 路由模式：`routes/admin_traces.py` 全文。
- 路由注册模式：`routes/route_registry.py` 中已有的 `admin_traces` 注册行。

### 6.3 验证清单

- [ ] `tests/test_gray_metrics.py`：
  - 模拟 `semantic_cache_event("hit", latency_ms=5.0)` 两次 + `miss` 一次，断言 `hit_rate == 2/3`。
  - 模拟 `instructor_intent_event(..., success=True)` + latency event，断言成功率和延迟百分位非零。
  - 调用 `reset_metrics()` 后所有 gray 计数归零。
- [ ] `tests/test_admin_metrics_gray.py`：
  - 用 `TestClient` 访问 `/admin/api/metrics/gray`，验证 `verify_admin` 生效。
  - 验证命中率和延迟字段存在且为数值。
- [ ] `ruff check .`、`ruff format --check`、`pyright observability/metrics.py routes/admin_metrics.py` 通过。
- [ ] `scripts/check_code_size.py` 通过（新增文件 ≤300 行，函数 ≤50 行）。

---

## 7. Phase 2：Trace 语义 enrichment

### 7.1 做什么

在 P4-8 trace 的 span metadata 中补充灰度观测字段，使 `/admin/api/traces/recent` 能直接看到每个请求是否命中缓存、是否走了 Instructor。

1. **`routing_engine.py` 中 classify/cache 相关 span**
   - 在调用 `routing_engine_cache.lookup_cached_response()` 前后包一个 `trace_span("semantic_cache")`。
   - span metadata 写入：
     - `cache_enabled`（bool）
     - `cache_status`："hit" / "miss" / "skip" / "error"
     - `cache_similarity`（命中时）
     - `cache_lookup_ms`
   - 在 intent 分类处包一个 `trace_span("intent")`：
     - `intent_source`："rule" / "instructor" / "fallback"
     - `instructor_confidence`（若来自 instructor）
     - `instructor_latency_ms`
2. **`routing_engine_helpers.py` / `routing_intent.py`**
   - 把 intent 来源和 instructor 结果透传到 `route()` 的 trace 中；可在 `RouteResult` metadata 中携带，或写入当前 trace span。
3. **`context_pipeline/tracing.py`**
   - 无需修改导出格式；metadata 已随 span 进入 `export()`。
   - 确保 `RequestTrace.export()` 包含所有 span metadata（当前已实现）。

### 7.2 参考代码位置

- P4-8 trace_span 用法：`routing_engine_trace.py` 全文。
- routing_engine 插桩位置：`routing_engine.py` 中 `_classify_and_recall()` 与主 `route()`。
- Trace 导出结构：`context_pipeline/tracing.py` 中 `RequestTrace.export()`。

### 7.3 验证清单

- [ ] `tests/test_tracing.py` 新增用例：
  - 构造一个请求，命中语义缓存，断言 `trace["spans"]` 中存在 `semantic_cache` span 且 `cache_status == "hit"`。
  - 构造一个低置信度请求触发 instructor，断言 `intent_source == "instructor"`。
- [ ] `/admin/api/traces/recent` 返回的 trace 中包含 `gray` 相关 metadata。
- [ ] 禁用缓存时 `cache_status == "skip"`，不产生异常。

---

## 8. Phase 3：灰度开关、安全默认与文档

### 8.1 做什么

1. **保持默认关闭**
   - `.env.example` 中 `LIMA_INSTRUCTOR_INTENT_ENABLED=0`、`LIMA_SEMANTIC_CACHE_ENABLED=0` 保持不变。
   - 代码中所有读取必须返回 `False` 当变量缺失或格式错误。
2. **失败安全**
   - `routing_intent_instructor.py` 已处理 `result is None` 和异常（发出 failure 事件并返回 None）。
   - `routing_engine_cache.py` 中 lookup/store 的 `except Exception` 必须记录 warning 并继续主流程（当前已实现，需保留）。
3. **新增运行时健康检查（可选但推荐）**
   - 在 `/health` 或 `/admin/api/config` 中暴露：
     - `instructor_intent_enabled`
     - `semantic_cache_enabled`
   - 便于灰度期间确认开关状态。
4. **更新文档**
   - `docs/superpowers/plans/README.md`：新增 P4-后续-灰度观测行，状态 🚧 进行中 → 完成后 ✅。
   - `STATUS.md`：记录本切片进入实施。
   - `progress.md`：记录 Phase 1–4 完成证据。
   - `.env.example`：在灰度开关注释中补充「灰度观测期间请同时开启 `LIMA_TRACING_ENABLED=1`」。

### 8.2 参考代码位置

- 开关读取：`config/env.py` 第 186–227 行、`semantic_cache/config.py` 第 10–12 行。
- 健康端点：`routes/health.py` 或 `routes/admin_extra_config.py`。
- 文档更新约定：`docs/superpowers/plans/README.md` 第 77–81 行「文档维护约定」。

### 8.3 验证清单

- [ ] 未设置 `LIMA_INSTRUCTOR_INTENT_ENABLED` 时，`instructor_intent_enabled()` 返回 `False`。
- [ ] 未设置 `LIMA_SEMANTIC_CACHE_ENABLED` 时，`cache_enabled()` 返回 `False`。
- [ ] 测试在开关关闭时直接通过，不走 instructor/cache 路径。
- [ ] 文档中的状态标记与代码一致。

---

## 9. Phase 4：测试、检查、VPS 灰度部署与验证

### 9.1 做什么

1. **本地验证**
   - `python -m pytest tests/test_gray_metrics.py tests/test_admin_metrics_gray.py tests/test_tracing.py -v`
   - `python -m pytest -m "not network" -q`（完整回归）
   - `ruff check .`
   - `ruff format --check`
   - `pyright observability/metrics.py observability/events.py routing_engine_cache.py routing_intent_instructor.py routes/admin_metrics.py`
   - `python scripts/check_code_size.py`
2. **VPS 灰度部署**
   - 使用 `python scripts/deploy_unified.py --slice core` 部署。
   - 通过脚本备份 VPS `.env`，**追加**（而非覆盖）以下变量：
     ```ini
     LIMA_INSTRUCTOR_INTENT_ENABLED=1
     LIMA_SEMANTIC_CACHE_ENABLED=1
     LIMA_TRACING_ENABLED=1
     ```
   - 重启服务。
3. **线上观测**
   - 冒烟：`curl -sf https://chat.donglicao.com/health`
   - 发送聊天请求，检查响应头 `X-LiMa-Trace-Id` 存在。
   - 间隔访问：
     ```bash
     curl -H "Authorization: Bearer $LIMA_ADMIN_TOKEN" \
       'https://chat.donglicao.com/admin/api/metrics/gray'
     ```
   - 检查 `/admin/api/traces/recent?limit=20` 中的 `cache_status` / `intent_source`。
4. **数据收集**
   - 运行 24–48 小时真实流量。
   - 记录：语义缓存命中率、命中延迟 P95；Instructor 调用成功率、平均延迟、意图与规则分类一致性。
5. **决策记录**
   - 若语义缓存命中率 < 30% 或 Instructor 成功率 < 80%，分析阈值/模型/embedding 是否需要调优。
   - 更新 `findings.md` 与 `STATUS.md`，决定是否默认开启。

### 9.2 回滚方案

- 立即回滚：在 VPS `.env` 中把两个开关改回 `0` 并重启。
- 代码回滚：使用 `scripts/deploy_unified.py` 的备份机制恢复到上一版本。

---

## 10. 验收标准

| 编号 | 验收项 | 通过标准 |
|------|--------|----------|
| A1 | 指标暴露 | `/admin/api/metrics/gray` 返回语义缓存和 Instructor 的命中率/延迟/计数 |
| A2 | Trace enrichment | `/admin/api/traces/recent` 中每条 trace 可见 `cache_status` 和 `intent_source` |
| A3 | 安全默认 | 开关默认关闭；缺失/错误配置不抛异常，继续主流程 |
| A4 | 测试覆盖 | 新增 ≥3 个测试文件，gray 指标/端点/trace enrichment 均覆盖 |
| A5 | 代码质量 | `ruff`、`pyright`、`check_code_size` 全部通过 |
| A6 | 灰度部署 | VPS 真实流量运行 ≥24h，收集到有效指标 |
| A7 | 文档同步 | `README.md` 追踪器、`STATUS.md`、`progress.md`、`.env.example` 已更新 |

---

## 11. 与 P4-8 全链路追踪的衔接点

| P4-8 产物 | 本切片用法 |
|-----------|------------|
| `context_pipeline/tracing.py` 的 `RequestTrace` | 在 span metadata 中写入 cache/intent 字段 |
| `routing_engine_trace.py` 的 `trace_span()` | 包裹 cache lookup 和 intent classification |
| `routes/chat_endpoints.py` 的 `X-LiMa-Trace-Id` | 用户请求头可关联到 `/admin/api/traces/recent` 的 enriched trace |
| `routes/admin_traces.py` | 新增 `/admin/api/metrics/gray` 与之并列，组成灰度观测 Admin 面板 |
| `observability/metrics.py` 的 ring buffer | 新增 gray 计数器，复用已有锁和 reset 机制 |

---

## 12. 风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| Instructor API 调用增加成本 | 中 | 仅在灰度环境开启，设定 timeout=10s 和 max_retries=2；观测后决定是否值得 |
| 语义缓存 fake embedder 命中率低 | 低 | 灰度期间可配置 `JINA_API_KEY` 切换真实 embedder；记录对比数据 |
| 指标代码引入锁竞争 | 低 | 复用已有 `_lock`；每次只更新计数器，不阻塞 I/O |
| Admin 端点泄露敏感信息 | 低 | 不写入原始 query/response；依赖 `verify_admin`；metadata 经过 `_sanitize_metadata` |

---

## 13. 建议的下一步动作

1. 审查并批准本计划。
2. 实施 Phase 1（指标暴露）。
3. 实施 Phase 2（Trace enrichment）。
4. 实施 Phase 3（开关、文档、安全默认）。
5. 本地测试 + 部署到 VPS 灰度环境，运行 24–48 小时。
6. 根据数据决定是否默认开启，并关闭本切片。
