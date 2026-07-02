# LiMa 子系统热度分层评估（Hot / Warm / Cold）

> 版本：2026-06-25
> 范围：代码质量治理计划 Q7 产出，已同步编码能力退役（2026-06-24）与 P1-9 清理结果
> 审计对象：`context_pipeline/`、`provider_probe/`、`provider_automation/`。`orchestrate*` 与 `scripts/eval_loop*` 已按 `DEPRECATED v3.0` 于 2026-06-26 物理删除。

## 1. 目的

LiMa 已完成从「个人编码助手后端」到「AI 智能设备统一云端服务」的战略转型，但仓库仍保留大量历史实验性子系统。本文档按**生产热路径参与度**对指定模块做 **hot / warm / cold** 分层，供后续瘦身、门禁拆分和文档归档决策使用。

**本文档不产生代码变更**；仅记录证据与建议优先级。

## 2. 分层定义

| 层级 | 含义 | 生产期望 | 典型处置 |
|------|------|----------|----------|
| **Hot** | 每次（或绝大多数）`/v1/chat`、设备任务、路由决策会同步触及 | 必须可测试、无静默降级、单文件 ≤300 行 | 保留、加固、聚焦 pytest |
| **Warm** | 启动时、异步后台、或条件分支（编码/复杂聊天/准入叠加）触及 | 默认开启或显式 env 开启；失败须打日志 | 保留但隔离边界；避免膨胀进 hot 文件 |
| **Cold** | 运维脚本、实验评估、浏览器探测、离线准入流水线 | 不得被 `server.py` / 热路径 import | 迁 `scripts/`、文档标注 optional、长期考虑归档 |

## 3. 规模快照（2026-06-16）

| 子系统 | Python 文件数 | 约行数 | 生产 import 面（非测试） |
|--------|----------------|--------|-------------------------|
| `context_pipeline/` | 27（含 `lab/` 2） | ~3,000 | 宽（路由、后处理、会话学习） |
| `provider_probe/` | 21 | ~2,253 | 极窄（几乎仅自引用 + 1 个测试） |
| `provider_automation/` | 13 | ~2,193 | 窄（启动准入叠加 + adapter） |
| `orchestrate*` + `scripts/eval_loop*` | **已删除** | — | — |

> 行数由仓库内 `*.py` 逐文件统计；与 `scripts/repo_stats.py` 全库统计口径不同。CP-1/CP-2/CP-4 后 `context_pipeline` 已从 ~40 文件瘦身。

## 4. 总览矩阵

| 子系统 | 默认层级 | 设备热路径 | 聊天热路径 | 建议 |
|--------|----------|------------|------------|------|
| `context_pipeline`（核心注入） | **Hot** | 间接（路由质量） | 是 | 保留；继续按域拆分超标文件 |
| `context_pipeline`（实验/评估） | **Cold** | 否 | 否 | 禁止默认启动；迁出或 gate |
| `provider_probe` | **Cold** | 否 | 否 | 与 `probe_loop.py` 区分；保持离线 |
| `provider_automation` | **Warm → Cold** | 否 | 否（仅准入叠加） | 启动只读 overlay；流水线 offline |
| `orchestrate*` + `scripts/eval_loop*` | **已删除** | 否 | 否 | 2026-06-26 物理删除；不再参与任何路径 |

**重要区分**：`probe_loop.py`（`server_lifespan` 启动的后端探活线程）**不属于** `provider_probe/` 包；后者是「新提供商发现 / 浏览器逆向 / 后端生成」实验流水线。

---

## 5. `context_pipeline/` 细分

### 5.1 Hot（生产主路径）

| 模块 | 触及点 | 证据 |
|------|--------|------|
| `retrieval_injection.py` | 路由前上下文注入 | `routing_engine.py`、`request_context_preflight.py` |
| `skill_store.py` | 技能召回 / 结晶 | `routing_engine_context.py`、`route_post_process.py` |
| `routing_weights.py` | 学习环路权重持久化 | `routes/ops_metrics` eval apply、selector 排序 |

**风险**：Hot 子集外仍有 ~20 个 Warm 根目录文件 + `lab/` 冷工具；新人易误判「整个目录都在热路径」。见 `context_pipeline/README.md` 与 `docs/context_pipeline_lab_CN.md`。

### 5.2 Warm（条件 / 后台 / 后处理）

| 模块 | 触及点 | 说明 |
|------|--------|------|
| `auto_indexer.py` | `server_lifespan` 可选启动 | 依赖本地索引；非请求关键路径 |
| `response_processors.py` / `response_pipeline.py` | `route_post_process` | 质量分、后处理链 |
| `narrative.py` | `route_post_process` handoff | 低流量 narrative 重构 |
| `routing_bridge.py` | selector / 权重桥接 | 与 ML 权重实验相关 |
| `cache.py` | 检索加速 | 受 env / 依赖可用性影响 |
| `event_log.py` | 结构化事件 | 可观测性辅链 |

### 5.3 Cold（实验、评估、测试台）

| 模块 | 说明 |
|------|------|
| `lab/static_analysis.py` | **已删**（CP-4 迁入 lab，2026-06-17 删除；原仅测试引用） |
| `retrieval_eval.py`、`retrieval_eval_runner.py` | **已删**（CP-2） |
| `ensemble.py`、`evolution.py`、`reflection.py` | **已删**（CP-1/CP-2） |
| `graph_retrieval.py`、`code_scanner.py`、`semantic_code_retrieval.py`、`reranking.py` | **已删除**（2026-06-26）；原 Warm/Cold 评估模块退役 |
| `complexity.py` | Warm lazy；仍以测试为主，保留根目录 |

### 5.4 建议（`context_pipeline`）

1. **P0**：在 `context_pipeline/README.md` 标注 Hot 五文件清单（2026-06-15 已完成）；`docs/REQUEST_PIPELINE_AUTHORITY_CN.md` 可交叉引用。
2. **P1**：Cold 模块目录前缀或 `docs/` 侧车说明「非生产默认」；`auto_indexer` 保持 env gate（已有 lifespan try/import 模式）。
3. **P2**：超标 hot 文件继续拆分（如 `retrieval_injection.py` 若 >300 行）；**CP-4 首批**已将 `static_analysis` 迁入 `context_pipeline/lab/`（2026-06-16）。

---

## 6. `provider_probe`（整体 **Cold**，CP-5 归档）

### 6.1 结构与用途

```
packages/provider-probe-offline/provider_probe/
  discovery/   # 网页搜索、中文平台、GitHub 监控、browser_probe
  reverse/     # API/鉴权/定价逆向
  verify/      # 连通性、coding eval、稳定性监控
  integrate/   # 后端常量生成、通知
```

根目录 `provider_probe/README.md` 仅为指针，无 Python 实现。

### 6.2 生产耦合证据

| 检查项 | 结果 |
|--------|------|
| `server_lifespan.py` import | **无** `provider_probe` |
| `routes/*` import | **无** |
| 非测试 import | 仅 `backend_generator` 注释字符串、独立 `browser_service.py` CLI |
| 测试 | `tests/test_browser_service.py` |

### 6.3 建议

1. **保持 Cold**：不得在 `server.py` 或路由注册中默认挂载。
2. **文档**：[`packages/provider-probe-offline/README.md`](../packages/provider-probe-offline/README.md)、[`provider_probe_offline_CN.md`](provider_probe_offline_CN.md)。
3. **瘦身候选**：`integrate/backend_generator.py` 生成物应经人工 review 后合入 `backends_registry`，禁止自动写热路径。
4. **勿与 `probe_loop.py` 合并**：后者是运行时健康探活（Warm），职责不同。

---

## 7. `provider_automation/`（**Warm 叠加 / Cold 流水线**）

### 7.1 生产触及点

| 路径 | 层级 | 证据 |
|------|------|------|
| `backend_admission_store.apply_startup()` | Warm | `server_lifespan.py` → 读取 `data/backend_admission.json` overlay |
| `adapters/cloudflare.py`、`adapters/gitee_ai.py` | Warm | `backend_admission_store.build_*` |
| `catalog` / `probe` / `runner` / `admission` 全流水线 | Cold | 仅测试 + 运维脚本（如 `scripts/inventory_gitee_ai_models.py`） |

### 7.2 原则对齐

与 [`docs/archive/strategic-plans-2026-06/PROJECT_OPTIMIZATION_ROADMAP_CN.md`](docs/archive/strategic-plans-2026-06/PROJECT_OPTIMIZATION_ROADMAP_CN.md) 一致：**提供商准入基于证据，而非可用性**。自动化流水线产出的是 **candidate / watchlist**，不得自动 `ROUTING_ENABLED`。

### 7.3 建议

1. **P0**：维持「catalog 存在 ≠ 可路由」测试（`test_provider_automation_admission.py` 已覆盖）。
2. **P1**：将 `runner` + `openrouter` live fetch 类入口限制在 CLI / CI job，强制 `LIMA_OPENROUTER_LIVE_FETCH=1` gate（已有测试）。
3. **P2**：Warm 层仅保留 `adapters/*` + snapshot 读路径；其余迁 `scripts/provider_automation/` 为可选后续（需并行期 shim）。

---

## 8. `orchestrate*`（**已删除**，2026-06-26）

`orchestrate.py`、`orchestrate_detect.py`、`orchestrate_pipeline.py`、`orchestrate_constants.py` 以及 `scripts/eval_loop*` 已按 `DEPRECATED v3.0` 物理删除。

- 原入口 `routes/chat_handler_dispatch.py` 中的 `needs_orchestration()` 已永远返回 `False`，实际路径不再调用编排逻辑。
- `routes/chat_stream.py` 与 `routes/chat_handler_dispatch.py` 的 orchestrate 引用链已断开。
- 设备路径本来就不使用 orchestrate；删除后与 `device_gateway/model_routing.py` 的边界更清晰。

如需复杂多域聊天编排，应在独立 spec 中重新设计，而不是恢复旧模块。

---

## 9. 推荐执行顺序（战略瘦身，非 Q7 代码）

| 优先级 | 动作 | 目标子系统 | 类型 |
|--------|------|------------|------|
| P0 | 文档标注 Hot 五文件 + `probe_loop` ≠ `provider_probe` | context_pipeline、probe | 文档 |
| P1 | Cold 模块 env/启动 gate 审计（禁止 silent import） | context_pipeline lab、provider_probe | 门禁 |
| P2 | `provider_automation` CLI 与 overlay 读路径分离 | provider_automation | 结构 |
| P3 | `context_pipeline/lab/` 物理搬迁 | context_pipeline cold | 重构（需设计文档） |
| P4 | `provider_probe` 归档为 `packages/provider-probe-offline/` | provider_probe | 运维（**CP-5 已关**） |

**下一批可执行清单**（含 CodeGraph `--fanin` 证据与批次验证命令）：[`CODEBASE_COLD_PRUNE_PRIORITY_CN.md`](CODEBASE_COLD_PRUNE_PRIORITY_CN.md)

---

## 10. 验证与复现

```powershell
# 规模复现（Q7 审计口径）
python -c "from pathlib import Path
def stat(p):
 p=Path(p); fs=list(p.rglob('*.py')) if p.is_dir() else [p]
 print(p, len(fs), sum(len(f.read_text(encoding='utf-8').splitlines()) for f in fs))
for x in ['context_pipeline','provider_probe','provider_automation']:
 stat(x)"

# Hot 路径回归（context）
python -m pytest tests/test_retrieval_injection.py tests/test_routing_intent.py -q

# provider_automation 准入不变量
python -m pytest tests/test_provider_automation_admission.py -q
```

---

## 11. 相关文档

| 文档 | 关系 |
|------|------|
| [`docs/archive/strategic-plans-2026-06/PROJECT_OPTIMIZATION_ROADMAP_CN.md`](docs/archive/strategic-plans-2026-06/PROJECT_OPTIMIZATION_ROADMAP_CN.md) | 设备路由与准入战略（已归档） |
| [`REQUEST_PIPELINE_AUTHORITY_CN.md`](REQUEST_PIPELINE_AUTHORITY_CN.md) | 聊天热路径 18 步 |
| [`archive/superpowers-2026-06/2026-06-15-code-quality-governance-plan.md`](archive/superpowers-2026-06/2026-06-15-code-quality-governance-plan.md) | Q0–Q7 治理计划（已关闭） |
| [`../tests/README.md`](../tests/README.md) | 聚焦门 / 全量门 |
| [`../AGENTS.md`](../AGENTS.md) | `context_pipeline.factory` 禁止作为唯一 pipeline |

---

## 13. 2026-06-16 大子系统审计（续 Q7）

> 审计范围：`search_gateway`、`channel_gateway`、`routes/` + 全仓冷模块扫描
> 基数：794 文件 / 93,145 行 → 审计后：735 文件 / 85,203 行（**-59 文件 / -7,942 行**）

### 13.1 已退役模块

| 模块 | 文件数 | 约行数 | 处置 | 理由 |
|------|--------|--------|------|------|
| `channel_gateway/` | 23 + 1 路由 + 13 测试 | ~3,500 | **整体退役** | WeChat 绑定层，生产 0 importer；`channel_retirement.py` 已标记 |
| `research/` | 4 + 1 测试 | ~290 | 删除 | 非测试代码 0 import |
| `web_reverse_eval.py` | 1 + 1 测试 | ~265 | 删除 | 非测试代码 0 import |
| `cli_status.py` | 1 + 1 测试 | ~214 | 删除 | 非测试代码 0 import |
| `sandbox/` | 2 + 1 测试 | ~254 | 删除 | 非测试代码 0 import |
| `data_workbench/` | 3 + 1 测试 | ~262 | 删除 | 非测试代码 0 import |
| `ops_entrypoint/` | 3 + 1 测试 | ~40 | 删除 | 非测试代码 0 import |
| `search_gateway/zhihu_adapter.py` | 1 | ~143 | 删除 | 生产 0 引用 |
| `search_gateway/public_feeder.py` | 1 | ~364 | 删除 | 生产 0 引用 |
| `search_gateway/policy.py` | 1 + 测试片段 | ~80 | 删除 | channel_gateway 退役后 0 引用 |
| `search_gateway/codesearch_status.py` | 1 | ~59 | 删除 | 0 引用 |
| `eval_loop.py` | 1 | ~51 | 删除 | 死 shim，全仓 0 import |
| 空目录（evals/、fragments/ 等） | — | 0 | 删除 | 无 .py 文件 |

### 13.1.2 2026-06-26 第二批：编码能力退役 shim 删除

| 模块 | 文件数 | 约行数 | 处置 | 理由 |
|------|--------|--------|------|------|
| `orchestrate*.py`（4 文件） | 4 | ~440 | **物理删除** | 复杂聊天编排；设备战略不依赖；`needs_orchestration()` 永远返回 `False` |
| `eval_*.py`（8 文件） | 8 | ~1,200 | **物理删除** | 编码评测冷工具；无热路径调用 |
| `periodic_coding_eval.py` | 1 | ~180 | **物理删除** | 周期编码评估后台线程；随编码能力退役 |
| `coding_backend_scorer.py` | 1 | ~120 | **物理删除** | 编码后端打分器；无热路径调用 |
| `backends_constants_code_tools.py` | 1 | ~60 | **物理删除** | 编码工具常量 facade；已合并 |
| `context_pipeline/{code_scanner,semantic_code_retrieval,code_context_injection,graph_retrieval,reranking}.py` | 5 | ~800 | **物理删除** | 编码上下文与检索实验模块；设备路径不使用 |
| `routes/xiaozhi_compat/` + `xiaozhi_v1_compat.py` | 6 + 13 测试 | ~2,400 | **物理删除** | 已由 `/device/v1/app/*` 原生管理面替代 |

### 13.2 search_gateway 保留清单（lazy import 保护）

以下适配器看似无直接 import，但被 `dev_adapter.py` 函数内 **lazy import** 引用，**禁止删除**：

- `brave_adapter.py`、`tavily_adapter.py`、`tinyfish_transport.py`、`anysearch_adapter.py`、`searxng_adapter.py`
- `codesearch_adapter.py`、`gemini_native.py`、`gitee_tools.py`

### 13.3 连锁效应

channel_gateway 退役后，其作为 search_gateway 主要消费者的引用消失，导致 `codesearch_status.py` 和 `policy.py` 变为 0 引用，已连锁清理。

---

## 14. 结论

- **`context_pipeline`**：核心价值在 **Hot 五模块**；其余大量文件为 Warm/Cold，是仓库行数膨胀主因之一，应用分层治理而非「整包删除」。
- **`provider_probe`**：整体 **Cold**，与运行时 `probe_loop` 无关；适合离线运维，不适合接入设备/聊天热路径。
- **`provider_automation`**：生产仅 **Warm overlay 读路径**；完整探测/准入流水线为 **Cold**，须维持人工审批边界。
- **`orchestrate*` + `scripts/eval_loop*`**：**已删除**（2026-06-26 按 `DEPRECATED v3.0` 清理）；不再属于任何分层。

**Q7 关闭标准**：本文档已落盘并被 `docs/README.md` 索引；不要求本阶段代码删除或搬迁。

---

## 15. 附录：2026-06-17 G3 小批冷区清理

在代码质量门禁整改后，按本文档分层原则执行一轮小批删除：只处理已确认无生产/测试引用的独立模块，不触及热路径。

### 15.1 本次删除清单

| 文件 | 行数 | 原分层 | 删除理由 |
|------|------|--------|----------|
| `search_gateway/dev_tools.py` | 279 | Cold | 无 import、无字符串引用；`tool_gateway/registry.py` 仅注册同名 tool 字符串，未调用其中函数 |
| `session_memory/hooks.py` | 61 | Cold | `on_request_start/on_response_complete/on_error` 无任何调用或导入 |
| `tool_gateway/executor.py` | 136 | Cold | `ToolExecutor` 无任何实例化或导入 |
| `infra/g4f_server.py` | 18 | Cold | 独立 g4f 启动脚本，无引用 |

合计删除 **494 行**。

### 15.2 验证

- ripgrep 确认上述文件模块名、顶层类/函数名在全库无引用；
- `python -m pytest --tb=short -q` → **1662 passed, 23 skipped, 0 failed**；
- `ruff check .` clean；
- 相关子系统 import (`tool_gateway.registry`、`session_memory.store`、`search_gateway`、`infra`) 无异常。

### 15.3 未删除的候选（留待后续批次）

- `deploy/path_proxy.py`、`deploy/deploy_prometheus_metrics.py`：独立部署脚本，无引用，但属于 `deploy/` 主题，不与本次冷模块混删。
- `packages/provider-probe-offline/provider_probe/*`：AGENTS.md 已标记为 **KEEP cold package**，保持离线探针能力，不删除。
