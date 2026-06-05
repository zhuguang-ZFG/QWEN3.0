# LiMa — 运行状态

> 2026-06-05 · VPS `47.112.162.80` · 分支 `codex/free-web-ai-probe`
> 权威架构见 `AGENTS.md`（全面重写版）+ `docs/REQUEST_PIPELINE_AUTHORITY.md`
> 产品定义见 `docs/PRODUCT_DEFINITION.md`
> M-OC0: LiMa CLI migrated to OpenCode MCP bridge. `lima-code` → `lima`. See `docs/opencode-integration.md`.

## 全部里程碑

| # | 内容 | LOCAL_ONLY_BACKENDS |
|---|------|---------------------|
| M0 | 设计文档 `docs/DECOUPLE_FROM_LOCAL_HOST.md` | — |
| M1 | 清理 oldllm_* + 删除 local_* Ollama | 37→22 |
| M2 | SCNet Large VPS sidecar | 22→18 |
| M3 | Kimi VPS sidecar | 18→15 |
| M4 | LongCat VPS sidecar | 15→12 |
| M5 | MiMo VPS sidecar | 12→7 |
| M6 | 删除 DDG + deepseek_free | 7→0 |
| M7 | 清理残留 + ESP32 删除 (-647 行) | 0 |
| M8 | MiMo-Reasonix 深度分析 | 0 |
| M9 | LiMa CLI 初始化 + 烟雾测试 | 0 |
| M10 | 文档更新 + 13 个过期文档标记 | 0 |
| M11a | ModelScope 8 后端加入路由池 | 0 |
| M11b | 代码审查修复 (2 issues) | 0 |
| M11c | cache-first compaction 移植 (deepcode-cli@649eb34) | 0 |
| M11d | 完整 ContextManager 移植 (+412 行, deepcode-cli@182730d) | 0 |
| M11e | 部署验证 + 文档更新 | 0 |
| M11f | 代码审查修复 (D:/GIT 硬编码) | 0 |
| M-OC0 | lima-code → lima 全局重命名 (98+74 files) | 0 |
| M-OC1 | OpenCode Phase 1 基础 IDE 适配 | 0 |
| M-OC2 | OpenCode Round 2 深度适配（overflow/normalize/usage/reasoning_effort） | 0 |
| M-OC3 | OpenCode Round 3 深度适配（reasoning_variants/session_options/stream_error） | 0 |
| M-OC4 | routing_executor 最小答案长度修复 (5→0) | 0 |
| M-OC5 | Admin Panel Apple UI 重设计 (admin.html +889/-330) | 0 |
| M-OC6 | AGENTS.md 全面重写 + 代码审查 (346 lines, 10 issues fixed) | 0 |
| M-OC7 | provider_kind 修复 (21 backends) + SSE 错误接线 + session ID + IDE 扩展 | 0 |

## 编码体验加厚（2026-06）

> **主线**：个人编码助手后端 → OpenCode/Cursor 客户端 → `routing_engine` + eval 证据驱动 IDE 默认池 → 加深可靠性（非再堆聊天模型）。
> 差距参考：`docs/VIBE_CODING_ANALYSIS.md` · 请求管线：`docs/REQUEST_PIPELINE_AUTHORITY.md`

| 切片 | 状态 | 权威模块 / 入口 |
|------|------|-----------------|
| P0 eval 驱动 IDE 默认池 | ✅ | `coding_pool_admission.py` · `data/coding_backend_tiers.json` · `scripts/build_coding_tiers_from_scores.py` |
| P1 OpenCode E2E + 流错误重试 | ✅ | `tests/test_opencode_e2e_cases.py` · `routing_executor.py`（`is_retryable` fallback） |
| P1 工具修复管线 MVP | ✅ | `tool_repair_pipeline.py` · `text_tool_extractor.py` · `workspace_sandbox.ReadTracker`（`LIMA_WORKSPACE_READ_GATE=1`） |
| P2 上下文注入 trace | ✅ | `context_injection_trace.py` · Admin `GET /api/context-injection-traces` · 响应 `x_lima_meta.context_injection` |
| P2 路由双轨收敛（渐进） | 🔄 | `routing_facade.py`（`/v1/status`、`ide_coder_pool`）· `router_http` → `http_caller` · `routes/agent_task_result_hooks.py` |

**Admin / 运维**

| 端点 / 命令 | 用途 |
|-------------|------|
| `GET /api/coding-pool-admission` | 证据门禁、tier 数量、demoted 摘要 |
| `GET /api/context-injection-traces` | 最近注入 trace（无密钥/无全文 prompt） |
| `python scripts/eval_coding_backends.py` | 跑 eval 并刷新 scores + tiers |
| `python scripts/build_coding_tiers_from_scores.py` | 仅从已有 scores 重建 tiers |

**环境变量**

| 变量 | 默认 | 含义 |
|------|------|------|
| `LIMA_IDE_POOL_EVIDENCE_GATE` | `1` | 无 eval/admission/tier 证据不进 IDE 默认池 |
| `LIMA_ROUTER_HTTP_HTTPX` | `1` | `router_http` 委托 `http_caller` |
| `LIMA_WORKSPACE_READ_GATE` | `0` | `1` 时 sandbox 未读文件禁止 edit |
| `LIMA_PERIODIC_CODING_EVAL` | `0` | `1` 启用周期性 coding eval |

**仍渐进（非方向问题）**：`smart_router` 部分调用方未迁完 — 见 [`docs/SMART_ROUTER_MIGRATION.md`](docs/SMART_ROUTER_MIGRATION.md)（调用方清单 + 6 slice 热路径顺序）；`docs/NEXT_MILESTONES.md` 与 `docs/superpowers/plans/` 仅作档案。

## 部署状态

| 服务 | 端口 | 状态 |
|------|------|------|
| lima-router | 8080 | ✅ active |
| scnet-large-reverse | 4505 | ✅ healthy |
| kimi-proxy | 4504 | ✅ healthy |
| longcat-web-proxy | 4506 | ✅ healthy |
| mimo-proxy | 4507 | ✅ healthy |

## VPS 已清理

| 进程 | 原因 |
|------|------|
| `frps.service` | FRP 隧道不再需要 |
| `duckai` 容器 | DDG 后端已删除 |
| `proxy.py` (port 8000) | deepseek_free 已删除 |

## 关键指标

| 指标 | 值 |
|------|-----|
| `LOCAL_ONLY_BACKENDS` | **空集合** |
| `BACKEND_PORT_ENV` | **空字典** |
| `DISABLED_HOST_DEPENDENT_BACKENDS` | **空字典** |
| 后端总数 | **184**（全部云端化） |
| ModelScope 后端 | 8 个（ms_deepseek_v4/qwen35/kimi_k25/glm5 + code 变体） |
| VPS reverse sidecar | 5/5 active |
| net code removed | ~650 行 |
| 总里程碑 | **26** 完成 |

## LiMa CLI — 维护模式

> **状态**: 已进入维护模式 — 不再添加新功能，仅修复关键问题
> 子模块 `deepcode-cli/` 保留，配置目录 `.lima/` 作为 OpenCode 配置参考
> 构建说明见 `docs/archive/lima-cli.md`

| 指标 | 值 |
|------|-----|
| 版本 | v0.1.25 |
| 测试 | 507 tests, 498 pass, 2 fail (需本地服务), 7 skip |
| ContextManager | ✅ 已移植 (+412 行) |
| 端到端烟雾测试 | ✅ |

## 测试

| 套件 | 通过 | 说明 |
|------|------|------|
| LiMa pytest | 2229 | 85 预存失败 (M-OC3 时点) |
| LiMa CLI | 498 | 2 预存失败 |

## 不再依赖的本机服务

| 服务 | 状态 |
|------|------|
| Ollama (port 11434) | ❌ 已删除 |
| DuckAI (port 4500) | ❌ 已删除 |
| TheOldLLM 代理 (port 4502) | ❌ 已迁移到 CF Worker |
| FRP 隧道 | ❌ 已停用 |
