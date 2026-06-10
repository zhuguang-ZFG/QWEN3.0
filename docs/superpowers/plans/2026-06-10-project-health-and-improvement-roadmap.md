# LiMa 项目健康诊断与改善路线图

> **For agentic workers:** 按里程碑执行；每步先测后合；设备路径与 Chat 路径分开验收。
>
> **Goal:** 在战略转型（智能设备云）与现有生产 Chat/OpenCode 之间建立清晰边界，修复 Phase 0 精简引入的回归，并按优先级补齐设备核心能力。
>
> **Architecture:** 双轨收敛——**设备热路径**（gateway → policy → planner → motion）与 **LLM 辅路径**（精简路由，非编码助手全栈）分离；Chat 栈逐步降级为维护模式。
>
> **Tech Stack:** Python 3.10, FastAPI, pytest, SQLite/Redis, VPS `chat.donglicao.com`

**日期:** 2026-06-10
**分支:** `feat/code-simplification`（当前工作上下文）
**状态:** 规划（待用户确认优先级）

---

## 一、项目再学习摘要

### 1.1 项目是什么

**LiMa** 是上海动力草科技的统一云端服务：对外提供 OpenAI/Anthropic 兼容 API（`server.py` → `routing_engine.py` → 170+ 后端），对内承载 **ESP32 绘图机/写字机** 的设备网关、任务调度与小智 App 兼容层。

| 维度 | 现状 |
|------|------|
| 产品定位（文档） | 2026-06-09 起从「个人编码助手」→「AI 智能设备云端服务」 |
| 生产入口 | `https://chat.donglicao.com`（nginx → uvicorn :8080） |
| 代码规模 | ~829 Python 文件、~11 万行业务代码；`routes/` 已精简至 43 文件 |
| 测试 | 216+ 测试文件；`run_pre_commit_check.py --full` 曾达 2074 passed |
| 战略阶段 | Phase 0 代码精简 ✅；Phase 1 硬件 AI M1–M4 ✅；M5+ 与绘图引擎待推进 |

### 1.2 核心子系统地图

```text
server.py
├── Chat 管线（仍占主复杂度）
│   routes/chat_endpoints.py → chat_handler → routing_engine
│   context_pipeline/（43 模块）· session_memory/ · skills_injector
│   http_caller → backends_registry（170+ 后端）
├── 设备管线（战略核心，相对独立）
│   device_gateway/（协议、任务、路径、MQTT/WS）
│   device_intelligence/（planner、simulator、shadow）
│   device_policy/ · device_workflow/ · device_ledger/
│   device_gateway/model_routing.py（Phase1 路由角色元数据）
├── 兼容层
│   routes/xiaozhi_v1_compat.py（28 REST 端点）
├── 运维
│   observability/ · provider_probe/ · scripts/deploy_unified.py
└── 已删除/弱化（Phase 0）
    semantic_cache · agent_runtime · tool_forward*（编码助手专属）
```

### 1.3 当前分支 `feat/code-simplification` 做了什么

- 删除 `semantic_cache`、`tool_forward`、`tool_forward_stream`、部分 `quality_gate` 子模块
- 保留 **临时 stub**：`quality_gate.py`、`anthropic_messages_handler.py`、`anthropic_vision_sse.py`
- `server.py` 将 `anthropic_native_*` 回调设为 **`None`**
- `routing_engine.py` 移除语义缓存分支（约 -20 行）
- 设备侧 M1–M4 + `model_routing` Phase1 已合入
- **未合入**（在 `codex/free-web-ai-probe` 等工作分支）：`/v1/responses`、OpenCode 快速路径、`health_bootstrap` 等

---

## 二、问题总结（按影响排序）

### P0 — 生产/功能回归

| ID | 问题 | 证据 | 影响 |
|----|------|------|------|
| R-01 | **工具调用路径断裂** | `chat_endpoints.py` L127-138 仍调 `anthropic_native_*`；`server.py` L111-112 注入 `None` | 任意带 `tools` 的 Chat 请求可能运行时失败（含 OpenCode Build） |
| R-02 | **OpenCode 优化未在当前分支** | 无 `routes/responses_endpoints.py`、`opencode_direct_stream` | Build 模式 `/v1/responses` 404；首条 10–30s |
| R-03 | **精简与生产用法冲突** | Phase 0 删 `tool_forward`，但 `chat_endpoints` 未改路由逻辑 | 战略上「弃编码助手」，实际上 Cursor/OpenCode 仍走 Chat API |
| R-04 | **分支碎片化** | `feat/code-simplification` vs `codex/free-web-ai-probe`；STATUS.md 仍写 `feat/kilo-provider-probe` | 修复散落、部署不确定 |

### P1 — 战略与架构债务

| ID | 问题 | 证据 | 影响 |
|----|------|------|------|
| A-01 | **双轨未收敛** | 文档称弃编码助手，但 `routing_engine` + `context_pipeline` 仍全量运行 | 维护成本高；设备场景不需要 web 搜索/代码检索/投机路由 |
| A-02 | **绘图引擎未独立** | 无 `xiaozhi_drawing/`；逻辑在 `device_gateway/path_pipeline` | 战略 Phase1 Week3-5「绘画引擎」缺口大 |
| A-03 | **设备状态内存化** | findings HAI-M1-4、M3-5、M4-6：ledger/workflow/policy 无跨进程持久化 | 重启丢状态；无法水平扩展 |
| A-04 | **model_routing 仅元数据** | `model_routing.py` 只打 `route_policy`，未接真实文生图/矢量化 | `draw_generated` 仍缺 DashScope/potrace 管线 |
| A-05 | **临时 stub 技术债** | 3 个 stub 文件 + `quality_check` 假通过 | 质量与 Anthropic 路径行为不可信 |

### P2 — 运维与质量

| ID | 问题 | 证据 | 影响 |
|----|------|------|------|
| O-01 | **VPS 内存紧张** | STATUS：部署时 `mem_available_mb=488` | 重启/并发时 OOM 风险 |
| O-02 | **公网 Cloudflare 限流** | E2E 公网 `_burst_` 挑战 | 外部验证不稳定 |
| O-03 | **测试套件分裂** | `conftest.py` 忽略 8+ 文件；Phase0 接受 5 failed | CI 信号失真 |
| O-04 | **文档编码/过期** | 战略 plan 部分乱码；STATUS 分支过时 | 新人 onboarding 困难 |
| O-05 | **全量 pytest 收集风险** | findings HAI-M1-5：缺失 `agent_runtime` 等模块引用 | `--full` 可能偶发 collection error |

### P3 — 长期

| ID | 问题 | 说明 |
|----|------|------|
| L-01 | 110k 行 vs 目标 55k | Phase 2 瘦身未启动 |
| L-02 | SQLite → 生产级 DB | 多设备/家庭场景需 PostgreSQL 或分库 |
| L-03 | 真机 HIL 证据不足 | M5+ 假设备测试多，硬件标定少 |
| L-04 | JDCloud 辅助节点 | 浏览器 probe 500、SSH key 未配 |

---

## 三、改善规划（分阶段）

### 阶段 0：止血与合并（1 周，P0）

**目标：** 当前分支可安全部署；OpenCode/工具调用不再 500。

| 任务 | 动作 | 验收 |
|------|------|------|
| 0.1 修复 tools 路径 | `chat_endpoints`：OpenCode + `LIMA_OPENCODE_TOOL_MODE=direct` 走 `handle_chat`；其他 clients 走 `routing_engine` 原生 OpenAI tools（或恢复精简版 `tool_forward`） | `tests/test_chat_endpoints.py` tools 相关通过 |
| 0.2 合并 OpenCode 修复 | Cherry-pick：`responses_endpoints`、`converters/responses_api`、`opencode_direct_stream`、health_bootstrap（若需要） | `opencode_real_verify.py --scenario all` PASS |
| 0.3 分支收敛 | 确定主线：`feat/code-simplification` 合入 probe 分支修复，或 rebase 后单分支部署 | 一份 `STATUS.md` 与 deploy 脚本对齐 |
| 0.4 部署验证 | VPS `.env`：`LIMA_OPENCODE_PREFERRED_BACKEND=scnet_ds_flash`、`LIMA_OPENCODE_DIRECT_STREAM=1` | 公网 + SSH 隧道 TTFB 对比记录到 findings |

**不做：** 大规模删 `routing_engine` 注入链（避免影响现有用户）。

---

### 阶段 1：设备核心补齐（3–5 周，战略 P0）

**目标：** 「画/写」闭环可在假设备上端到端演示。

| 周 | 里程碑 | 交付物 |
|----|--------|--------|
| 1 | **Chat 栈设备模式** | `LIMA_DEVICE_MODE=1` 跳过 web_search/code_context/skills 注入；设备对话走 `device_llm_router` 薄封装 |
| 2 | **model_routing Phase 2** | `device_draw` → DashScope/备用图生 API → SVG/路径；`device_write` 保持确定性 |
| 3 | **持久化 M1 扩展** | ledger/workflow SQLite 表 + migration；Redis 任务队列生产默认 |
| 4 | **xiaozhi 兼容审计** | 28 端点回归 + 真机 fake U8 联调脚本 |
| 5 | **删除 stub** | 移除 `quality_gate`/`anthropic_messages_handler` stub；Chat fallback 简化为顺序重试 |

参考：`2026-06-09-lima-hardware-ai-phase1-execution-plan.md` M5–M8。

---

### 阶段 2：代码瘦身与边界清晰（2–3 周）

**目标：** 代码量向 55k 行靠拢；职责清晰。

- 删除或归档：`smart_router` 门面（若 `routing_classifier` 已覆盖）
- 合并 `context_pipeline` 中设备场景零调用模块
- `routes/` 再减：Anthropic 专用路径若设备/App 不需要则移除
- 建立 **`docs/README.md` 导航** + 修复战略文档 UTF-8
- 测试：删除 ignore 列表中已不存在的测试；修复 Phase0 的 5 个失败用例或删 obsolete

---

### 阶段 3：运维与发布（持续）

| 项 | 建议 |
|----|------|
| VPS | 内存升至 ≥2GB 可用；或 Chat 与 Device 分进程 |
| 监控 | Prometheus 已有；补 device_task_latency、draw_pipeline_errors |
| 开发体验 | 文档化 SSH 隧道 + OpenCode 预热 `models.dev` |
| JDCloud | 仅 probe/metrics；修 8092 render 或禁用 browser 路径 |

---

## 四、优先级矩阵（建议执行顺序）

```text
本周必做          本月重点              季度目标
────────          ────────              ────────
R-01 tools 修复   A-04 绘图管线         L-01 代码减半
R-02 OpenCode     A-03 持久化           L-02 数据库升级
0.3 分支合并      删除 stub             真机 HIL
```

---

## 五、成功指标（可量化）

| 指标 | 当前（估） | 阶段 0 目标 | 阶段 1 目标 |
|------|-----------|-------------|-------------|
| OpenCode 首条 TTFB（隧道） | 10–30s | <8s | <5s（设备对话） |
| tools 流式 E2E | FAIL | PASS | PASS |
| `pytest --full` | ~2074 pass | 0 collection error | +device draw 集成测 |
| routes 文件数 | 43 | 43 | ≤38（去 stub） |
| draw_generated 真 SVG 产出 | 部分 | 假设备 PASS | 真机预览 PASS |

---

## 六、风险与原则

1. **永不无声降级**：删模块须改路由或显式 501 + 文档，禁止 `None` 回调。
2. **设备优先**：新功能默认走 `device_gateway` 契约测试。
3. **Chat 维护模式**：保留兼容但不再叠加编码助手特性。
4. **可回滚部署**：继续 `deploy_unified.py` 备份 + 文件级热更新。

---

## 七、建议的下一步（待你确认）

1. **立即执行阶段 0**（修复 R-01/R-02 + 合并分支）— 推荐
2. **暂停 Chat 优化，全力 device 绘图管线** — 若硬件上市紧迫
3. **维持现状，仅文档整理** — 不推荐（R-01 为实损）

---

**相关文档**

- 战略总纲：`docs/superpowers/plans/2026-06-09-lima-strategic-pivot-to-smart-devices.md`
- Phase 0 验证：`docs/archive/phase0-2026-06/2026-06-09-code-simplification-verification.md`
- 设备路由 Phase1：`docs/superpowers/plans/2026-06-10-device-model-routing-phase1.md`
- 架构：`docs/ARCHITECTURE.md`、`AGENTS.md`
