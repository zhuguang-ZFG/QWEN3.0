# LiMa Cold 子系统清理优先级表

> 版本：2026-06-16
> 依据：[`CODEBASE_SUBSYSTEM_TIER_CN.md`](CODEBASE_SUBSYSTEM_TIER_CN.md) + `python scripts/codegraph_orphans.py --fanin`
> 目标：在**不伤害设备热路径**与**聊天 Hot 五模块**前提下，继续「去缝合」

## 使用方式

1. **按批次执行**（P0 → P1 → …），每批独立 commit。
2. 删除前必跑：`python scripts/codegraph_orphans.py --fanin`（图内零引用 ≠ 可删，须看 lazy import）。
3. 每批门禁：`python -m pytest tests/test_retrieval_injection.py tests/test_routing_engine.py tests/test_device_gateway_model_routing.py -q` + `ruff check .`
4. 与设备路线图并行：**M13 发布证据模板优先于 P2 结构搬迁**。

---

## 总览

| 批次 | 风险 | 预估减行 | 类型 | 设备路径影响 |
|------|------|----------|------|--------------|
| **P0** | 低 | ~1.5k | 删纯测试冷模块 | 无 |
| **P1** | 低 | ~2k | 删离线评测链 | 无 |
| **P2** | 中 | ~4k | `provider_automation` CLI 迁 `scripts/` | 无 |
| **P3** | 中 | ~4k（首批 ~0.1k） | `context_pipeline/lab/` 物理搬迁 | 无（**CP-4 首批已关**） |
| **P4** | 高 | ~2.2k | `provider_probe` 归档为 JDCloud 部署包 | 无（**CP-5 已关**） |

**禁止整包删除**：`routing_engine*`、`device_gateway/*` Hot 路径、`session_memory` Hot facade、`probe_loop.py`（运行时探活 ≠ `provider_probe`）。

---

## P0 — 零生产 fan-in（**CP-1 已关闭 2026-06-16**）

已删除并清理生产 lazy import：

| 模块 | 状态 |
|------|------|
| `reflection.py` | ✅ 已删；`routing_bridge.reflect_and_adjust` 改为 no-op |
| `session_memory_enhancer.py` | ✅ 已删；`route_post_process` 块移除 |
| `artifact.py` | ✅ 已删；`http_sync` 句柄压缩退役 |
| `hierarchical_memory.py` + `memory_persistence.py` | ✅ 已删；`routing_selector` / `route_post_process` / `routing_bridge` 清理 |

**CP-1 保留（Warm/Hot lazy，勿删）**：`entity_extraction.py`（`retrieval_injection`）、`graph_retrieval.py`、`complexity.py`。

下一批见 **P1**。

---

## P0（历史规划 — 已由 CP-1 覆盖部分项）

CodeGraph 2026-06-16：`TEST-ONLY` 或图内 `ZERO`，且 `--fanin` 无生产命中。

| 模块 | 路径 | 证据 | 伴随删除 |
|------|------|------|----------|
| reflection | `context_pipeline/reflection.py` | ~~TEST-ONLY~~ **CP-1 已删** | — |
| hierarchical_memory | `context_pipeline/hierarchical_memory.py` | ~~lazy prod~~ **CP-1 已删** | — |
| memory_persistence | `context_pipeline/memory_persistence.py` | **CP-1 已删** | — |
| session_memory_enhancer | `context_pipeline/session_memory_enhancer.py` | **CP-1 已删** | — |
| entity_extraction | `context_pipeline/entity_extraction.py` | **保留** — `retrieval_injection` Hot lazy | — |
| 实验 artifact | `context_pipeline/artifact.py` | **CP-1 已删** | 勿与 `device_artifacts/` 混淆 |

**验证命令**

```powershell
python scripts/codegraph_orphans.py --fanin
python -m pytest tests/test_retrieval_injection.py tests/test_routing_engine.py -q
```

---

## P1 — 离线评测 / 进化实验链（**CP-2 已关闭 2026-06-16**）

已删除并清理生产 lazy import：

| 模块 | 状态 |
|------|------|
| `retrieval_eval.py` + `retrieval_eval_runner.py` | ✅ 已删；`tests/test_retrieval_eval_fixture.py` 移除 |
| `evolution.py` + `signal_extraction.py` | ✅ 已删；`routing_selector` / `routing_bridge` 清理 |
| `local_retrieval/eval_bridge.py` | ✅ 已删 |

**CP-2 保留（Warm/Hot）**：`production_index.py` + `retrieval_corpus.py`（`retrieval_injection`）、`graph_retrieval.py`、`complexity.py`。

下一批见 **P2（CP-3）**。

---

## P1（历史规划 — 已由 CP-2 覆盖）

仅测试或 `local_retrieval` 桥接，**不**在 `routing_engine.route()` 主链。

| 模块 | 说明 | 注意 |
|------|------|------|
| `retrieval_eval_runner.py` | **CP-2 已删** | — |
| `retrieval_eval.py` | **CP-2 已删** | — |
| `evolution.py` + `signal_extraction.py` | **CP-2 已删** | — |
| `production_index.py` + `retrieval_corpus.py` | **保留** | `retrieval_injection` lazy |

**勿放入 P1**（看似冷、实则 Warm/Hot lazy）：

| 模块 | 生产触及 |
|------|----------|
| `complexity.py` | `routing_engine_context.py` |
| `graph_retrieval.py` | `retrieval_injection.py`、`code_scanner.py`、`lima_mcp` |
| `graph_context_expander.py` | `code_context_injection.py` lazy |
| `retrieval_trace.py` | `retrieval_injection.py`、`ops_metrics`、`admin_api` |

---

## P2 — `provider_automation` 结构与 CLI 分离（CP-3）✅ 已关闭 2026-06-16

生产仅 **Warm overlay 读路径**（`server_lifespan` → `backend_admission_store.apply_startup()`）。

| 动作 | 保留（Warm） | Cold / 运维入口 |
|------|--------------|-----------------|
| 准入边界 | `adapters/*`、`backend_admission_store.py`、`catalog.py`（类型枚举） | `runner.py`、`probe.py` 等全流水线 |
| CLI | — | `scripts/provider_automation/run_probe_batch.py`（`LIMA_PROVIDER_AUTOMATION_RUN=1`） |
| 文档 | [`../provider_automation/README.md`](../provider_automation/README.md) | Warm/Cold 分层 + 不变量测试命令 |

**不变量**：`tests/test_provider_automation_admission.py`、`tests/test_provider_automation_runner.py` 通过；OpenRouter live fetch 保持 `LIMA_OPENROUTER_LIVE_FETCH=1` gate。

**原则**：catalog 存在 ≠ 可路由；自动化产出仅为 candidate/watchlist。

下一批见 **P3（CP-4）**。

## P3 — `context_pipeline/lab/` 物理搬迁（**CP-4 首批已关闭 2026-06-16**）

将 P0/P1 清理后仍残留的 Cold 文件迁入 `context_pipeline/lab/`，根目录只保留 Hot/Warm 生产面。设计说明：[`context_pipeline_lab_CN.md`](context_pipeline_lab_CN.md)。

**Hot（禁止动）**：`retrieval_injection.py`、`code_context_injection.py`、`skill_store.py`、`response_validator.py`、`routing_weights.py`

**CP-4 已迁 lab**：`static_analysis.py`（仅 `tests/test_static_analysis.py`）

**Warm（慎动，仍留根目录）**：`auto_indexer.py`、`response_processors.py`、`response_pipeline.py`、`narrative.py`、`routing_bridge.py`、`cache.py`、`semantic_code_retrieval.py`、`event_log.py`、`reranking.py`、`code_scanner.py`、`guardrails.py`、`tracing.py`、`token_budget.py`、`complexity.py`、`graph_retrieval.py`、`retrieval_trace.py` 等

**伴随清理（同批）**：删除 8 个 `agent_runtime` 遗留测试文件；移除 `tests/conftest.py` `collect_ignore_glob`；`run_pre_commit_check.py` 去掉不存在的 `test_semantic_code_retrieval.py` ignore。

下一批见 **P4（CP-5）**。

---

## P3（历史规划 — CP-4 首批）

将 P0/P1 清理后仍残留的 Cold 文件迁入 `context_pipeline/lab/`，根目录只保留：

**Hot（禁止动）**：`retrieval_injection.py`、`code_context_injection.py`、`skill_store.py`、`response_validator.py`、`routing_weights.py`

**Warm（慎动）**：`auto_indexer.py`、`response_processors.py`、`response_pipeline.py`、`narrative.py`、`routing_bridge.py`、`cache.py`、`semantic_code_retrieval.py`、`event_log.py`、`reranking.py`、`code_scanner.py`、`guardrails.py`、`tracing.py`、`token_budget.py`

---

## P4 — `provider_probe` 归档（**CP-5 已关闭 2026-06-16**）

| 项 | 说明 |
|----|------|
| 动作 | `provider_probe/` → `packages/provider-probe-offline/provider_probe/`；根目录仅 `provider_probe/README.md` 指针 |
| 设计 | [`provider_probe_offline_CN.md`](provider_probe_offline_CN.md) |
| 部署 | `deploy/jdcloud/*.sh` 源路径已更新 |
| 测试 | `tests/test_browser_service.py` + `pytest.mark.offline_probe`；`pytest.ini` `pythonpath` |
| 不变量 | `server_lifespan` / `routes/*` **无** import；仅 JDCloud 手动/定时 |

下一批见 **可选 P5**。

---

## P4（历史规划 — CP-5）

| 项 | 说明 |
|----|------|
| 现状 | 整体 Cold；`server_lifespan` / `routes/*` **无** import |
| 保留策略 | 代码可留仓，但仅 JDCloud `117.72.118.95` 手动/定时跑；禁止默认挂载 |
| 可选 | 抽成 `packages/provider-probe-offline/` 或独立 repo，主仓只留 README 指针 |
| 测试 | `tests/test_browser_service.py` 随包迁移或标 `@pytest.mark.external` |

---

## 可选 P5 — 默认关闭的表面（低优先级）

| 候选 | 条件 | 风险 |
|------|------|------|
| `routes/gitee_webhook.py` + `github_webhook.py` | 生产 `*_WEBHOOK_ENABLED=0` 且长期不用 | 中（有测试） |
| `lima_mcp/` 路由 | `route_registry` try-import；若产品不用 MCP 面 | 中（依赖 `graph_retrieval`） |
| ~~`channel_gateway/`~~ | ~~确认无活跃 G3 会话~~ | ~~高~~ **✅ 已退役 2026-06-17**（见下方 P6） |

**不建议**：为「少缝合」而删 `orchestrate*`（Warm 复杂聊天）；设备战略不依赖，但公共 API 仍可能触发。

---

## P6 — 大子系统审计瘦身（**2026-06-17 已完成**）

> 审计范围：`search_gateway`、`channel_gateway`、`routes/` + 全仓冷模块扫描
> 结果：794 文件 / 93,145 行 → 735 文件 / 85,203 行（**-59 文件 / -7,942 行**）

| 批次 | 动作 | 减行 |
|------|------|------|
| 空目录 + 死 shim | 删除 `eval_loop.py`、`evals/`、`fragments/`、`reverse_gateway/`、`routes/.omc/` | ~51 |
| 仅测试引用冷模块 | 删除 `research/`、`web_reverse_eval.py`、`cli_status.py`、`sandbox/`、`data_workbench/`、`ops_entrypoint/` + 测试 | ~1,325 |
| search_gateway 死适配器 | 删除 `zhihu_adapter.py`、`public_feeder.py` | ~507 |
| channel_gateway 整体退役 | 删除 23 文件 + `routes/channel_gateway.py` + 13 测试；`route_registry.py` 注册块移除；`channel_retirement.py` 标记 | ~3,500 |
| 连锁清理 | `codesearch_status.py`、`policy.py`（channel_gateway 退役后 0 引用） | ~139 |

**关键发现**：`search_gateway/dev_adapter.py` 和 `dev_tools.py` 在函数内做 lazy import，保护了 `brave_adapter`、`tavily_adapter`、`tinyfish_transport`、`codesearch_adapter`、`gemini_native`、`gitee_tools` 等适配器不被误删。详见 [`CODEBASE_SUBSYSTEM_TIER_CN.md`](CODEBASE_SUBSYSTEM_TIER_CN.md) §13。

**验证**：`ruff check .` clean；全量测试 1736 passed / 25 skipped / 4 pre-existing failures。

---

## 与活跃路线图对齐

| 路线图项 | 与清理关系 |
|----------|------------|
| **M13** 发布证据模板 | 先做；不阻塞 P0 |
| 阶段 2 真实 API fixture | 依赖 `eval_device_model_role.py`，与 P1 无冲突 |
| 阶段 4 聊天/设备测试拆分 | P3 完成后更易拆门禁 |
| U1 固件 route_policy | 无关 Cold 删除 |

---

## 复现审计

```powershell
# 规模（Q7 口径）
python -c "from pathlib import Path
for x in ['context_pipeline','provider_probe','provider_automation']:
 p=Path(x); fs=list(p.rglob('*.py')); print(x, len(fs), sum(len(f.read_text(encoding='utf-8').splitlines()) for f in fs))"

# 孤儿 + lazy 交叉
python scripts/codegraph_orphans.py --fanin

# Hot 回归
python -m pytest tests/test_retrieval_injection.py tests/test_routing_engine.py tests/test_orchestrate_route_context.py -q
python -m pytest tests/test_provider_automation_admission.py -q
python -m pytest tests/test_device_gateway_model_routing.py -q
```

---

## 相关文档

| 文档 | 关系 |
|------|------|
| [`CODEBASE_SUBSYSTEM_TIER_CN.md`](CODEBASE_SUBSYSTEM_TIER_CN.md) | Hot/Warm/Cold 定义与 Q7 结论 |
| [`PROJECT_OPTIMIZATION_ROADMAP_CN.md`](PROJECT_OPTIMIZATION_ROADMAP_CN.md) | 设备战略主轨 |
| [`../context_pipeline/README.md`](../context_pipeline/README.md) | Hot 五文件清单 |
| [`../progress.md`](../progress.md) | 2026-06-15 CodeGraph 瘦身证据 |
