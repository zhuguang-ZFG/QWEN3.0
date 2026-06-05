# LiMa 生产力增强计划 — 六能力 × 净新增资源

> **For agentic workers:** 文档先行；**默认关**；不为了接工具而改 `routing_engine` / `router_v3`；优先可审计、可回滚、可 smoke 的闭环。
>
> **Goal:** LiMa 当前最值得增强的不是「再多接几个聊天模型」，而是 **资源雷达、代码理解、运维诊断、检索入口、任务编排、硬件闭环** 六类生产力能力。
>
> **Status:** Active plan | **Created:** 2026-05-26
>
> **Related:** `docs/superpowers/plans/2026-05-25-productivity-infrastructure-review.md`、
> `docs/superpowers/plans/2026-05-26-infra-tools-integration.md`、
> `docs/superpowers/plans/2026-05-23-lima-dev-search-tools.md`、
> `docs/superpowers/plans/2026-05-25-lima-device-gateway-ha.md`、
> `docs/reference/MCP_CONNECTOR_CATALOG.md`、
> `docs/reference/EXTERNAL_CAPABILITY_RADAR_2026-05-24.md`、
> `AGENTS.md`

---

## 1. 战略定位

```text
                    LiMa 生产力层（本计划）
                              │
     ┌────────────────────────┼────────────────────────┐
     │                        │                        │
  资源雷达              代码理解                 运维诊断
  MCP/free tier         跨文件/参考仓            VPS/Redis/FRP/DG
  自动 inventory        语义搜索                 指标+日志+trace
     │                        │                        │
     └────────────────────────┼────────────────────────┘
                              │
     ┌────────────────────────┼────────────────────────┐
     │                        │                        │
  检索入口              任务编排                 硬件闭环
  免费搜索/文档抓取      smoke/eval/deploy        ESP32/DG
  知识摄取              可审计工作流             台账/孪生/OTA
```

**与「再接聊天模型」的边界：**

| 做 | 不做 |
|----|------|
| 让 Agent **发现**外部 MCP / free tier / 开源工具变化 | 未 smoke 的新模型自动进 `code_orchestrator` 主池 |
| 让 LiMa **更快定位**跨文件关系与公开参考实现 | 把 LiMa 私有代码发给第三方 SaaS 搜索 |
| 让 Operator **自己查** VPS/Redis/FRP/Device Gateway 指标与历史错误 | 再堆一个与现有 Telegram/health 重复且不可审计的告警通道 |
| 把 smoke / eval / deploy / digest **编排成可见工作流** | 引入需要长期专职运维的重型平台作为默认依赖 |
| 为 Device Gateway **借鉴**设备台账与数字孪生模型 | 第一天用 ThingsBoard 替换 LiMa 自有 gateway |

**原则（继承 Superpowers）：**

1. **文档先行** — 每个 Phase 有验收与 rollback 说明。
2. **默认关** — 新网络服务、MCP、自托管组件均 `*_ENABLED=0` 直到 smoke 写入 `progress.md`。
3. **只读优先** — MCP 雷达、searchcode、Netdata 查询先做 read-only；写操作需 approval gate。
4. **单文件 ≤300 行** — inventory 脚本、adapter、workflow 定义分拆。
5. **不提交密钥** — token 仅 VPS/本地 `.env`；catalog 与 plan 不含真实值。

---

## 2. 六类生产力能力

### PE-A — 资源雷达（Resource Radar）

**目标：** 自动发现 MCP registry、free tier、开源工具变化；**不是**直接安装工具。

| 能力 | 交付物 | 验收 |
|------|--------|------|
| MCP 只读 inventory | `scripts/inventory_mcp_registries.py` → `data/mcp_registry_snapshot.json` | dry-run 不报错；输出 server 名、分类、来源 URL |
| 候选区文档 | `docs/reference/MCP_CONNECTOR_CATALOG.md` 自动/半自动更新 **candidate** 区 | 与 Glama / Official Registry / SafeMCP 交叉去重 |
| Free tier 雷达 | 扩展现有 `provider_automation/` + CF/Gitee inventory 模式 | 每周 diff 报告；异常仅 Telegram ops（不进 chat 默认路径） |

**Discovery 源（只读）：**

- [Glama MCP Registry](https://glama.ai/mcp/servers) — 大量 MCP server 索引
- [Official MCP Registry](https://registry.modelcontextprotocol.io/)
- [SafeMCP](https://safemcp.com/) — 按分类列 MCP，便于打标签

---

### PE-B — 代码理解（Code Understanding）

**目标：** 更快定位跨文件关系、外部项目参考实现。

| 能力 | 工具 | 边界 |
|------|------|------|
| 公开参考实现搜索 | **searchcode MCP**（免费 beta） | 只查 **公开** GitHub/开源仓库；**不传** LiMa 私有代码 |
| 本地/参考仓语义搜索 | **codesearch MCP**（Rust，BM25 + vector + tree-sitter） | 索引 allowlist 目录；离线优先；比纯 `rg` 更懂语义 |
| LiMa 已有 | `search_repo`、graph retrieval、`dev_fetch_github_file` | 保持 LiMa-owned 为默认；外部 MCP 为 optional overlay |

**与 LiMa 集成路径：** 经 `lima_mcp/` 暴露 read-only 工具；不在 `routing_engine` 热路径默认启用。

---

### PE-C — 运维诊断（Ops Diagnostics）

**目标：** VPS、Redis、FRP、Device Gateway 出问题时，AI/Operator 能查指标、翻历史日志、追请求链路。

| 能力 | 工具 | 说明 |
|------|------|------|
| VPS 实时诊断 | **Netdata MCP** | Agent/Parent 自带 MCP；查 CPU/内存/磁盘/进程/网络/告警；**第一批优先** |
| 日志 + metrics + traces | **OpenObserve** 或 SigNoz | OpenObserve 单体更轻；SigNoz 更完整 OTEL。LiMa 选 **OpenObserve 优先**（见 §4） |
| 已有 | `infra/lima-health.bat`、Telegram `/health`、INF-B Healthchecks | 本计划 **补观察台**，不替换 dead-man |

**缺口证据：** `observability/events.py` 有事件，但缺「翻历史错误和请求链路」的 Operator 观察台（见 `2026-05-25-productivity-infrastructure-review` PROD-006/007）。

---

### PE-D — 检索入口（Search & Ingestion）

**目标：** 免费搜索、文档抓取、知识摄取 — 给 LiMa research / dev-search grounding。

| 能力 | 工具 | 护栏 |
|------|------|------|
| 自托管元搜索 | **SearXNG** | 免费 research 源；**必须**加缓存、冷却、来源标注；防上游限流 |
| 已有 | `search_gateway/`、百度千帆、TinyFish fallback | SearXNG 作为 **新增 tier**，不替换现有 gateway 权威边界 |
| 文档抓取 | 延续 `dev_read_url` + 未来 Firecrawl 候选 | SSRF、redact、audit 不变 |

**与 INF 计划关系：** `2026-05-26-infra-tools-integration.md` 曾暂缓 SearXNG；本计划将其升为 **PE-D 第一批**（自托管、默认关）。

---

### PE-E — 任务编排（Workflow Orchestration）

**目标：** smoke、eval、deploy、告警串成 **可审计** 工作流。

| 能力 | 工具 | 适用场景 |
|------|------|----------|
| 可见工作流引擎 | **Kestra Open Source** | 每日 smoke、free 模型探测、VPS health、GitHub/Gitee 事件、Telegram digest、eval gate |
| 自托管状态页 | **Uptime Kuma** | 公开 HTTPS、FRP、Device Gateway、模型代理端口；**可选**替代 Healthchecks.io SaaS |
| 已有 | cron + `scripts/deploy_*.py` + Telegram | Kestra **编排**现有脚本，不 rewrite 业务逻辑 |

**Phase 顺序：** 在 PE-C（可观测）和 PE-A（inventory）有 baseline 后再上 Kestra，避免「空编排」。

---

### PE-F — 硬件闭环（Device / ESP32 Loop）

**目标：** ESP32 / Device Gateway 的设备管理、OTA、数字孪生 — **借鉴参考**，不 Day-1 替换 LiMa gateway。

| 能力 | 工具 | LiMa 用法 |
|------|------|-----------|
| 设备管理 + 遥测 UI | **ThingsBoard CE**（Apache 2.0） | 参考设备台账、规则引擎、可视化；**不**替换 `device_gateway/` |
| 数字孪生状态模型 | **Eclipse Ditto** | 借鉴 desired / reported / current state + policy |
| ESP32 固件参考 | **ESPHome** | fake device、传感器样机、声明式 OTA/配置思路；**不**替代 U8 固件 |

**已有基础：** Redis HA task store、public smoke、`docs/superpowers/plans/2026-05-25-p0.1-esp32-motion-executor-contract.md`。

---

## 3. 净新增优先资源清单

| 资源 | 能力类 | 用途 | 边界 / 风险 |
|------|--------|------|-------------|
| Glama MCP Registry | PE-A | 外部 MCP 雷达数据源 | 只读 inventory；不自动 install |
| Official MCP Registry | PE-A | 权威 MCP 发现 | 同上 |
| SafeMCP | PE-A | 分类标签输入 | 同上 |
| searchcode MCP | PE-B | 公开代码智能搜索 | 仅公开仓库；无私有代码 |
| codesearch MCP | PE-B | 本地离线多仓语义搜索 | allowlist path；Rust 二进制部署 |
| SearXNG | PE-D | 自托管元搜索 | 缓存+冷却+来源标注；防限流 |
| OpenObserve | PE-C | 日志/metrics/traces 一体 | 单体部署；默认关；保留 rollback |
| SigNoz | PE-C | 完整 OTEL 栈（备选） | 更重；OpenObserve 不够时再评 |
| Netdata MCP | PE-C | VPS 实时诊断 | Agent on VPS；MCP read-only 优先 |
| Kestra OSS | PE-E | 工作流编排 | 包装现有 scripts；审计日志 |
| Uptime Kuma | PE-E | 自托管 uptime | 可选替 Healthchecks SaaS |
| ThingsBoard CE | PE-F | 设备台账/遥测参考 | 参考架构，不替 gateway |
| Eclipse Ditto | PE-F | 数字孪生模型参考 | 状态建模文档化 |
| ESPHome | PE-F | ESP32 能力/OTA 参考 | fake device 样机 |

---

## 4. 第一批实施（推荐顺序）

> **用户指定第一批 5 项** — 最贴 LiMa 当前生产力。

| 序 | ID | 资源 | 估时 | 路由风险 | 依赖 |
|----|-----|------|------|----------|------|
| 1 | **PE-C-1** | Netdata MCP | ~1 天 | 无 | VPS root/Agent 安装权限 |
| 2 | **PE-B-1** | codesearch MCP | ~1–2 天 | 无 | 本地索引路径 allowlist |
| 3 | **PE-D-1** | SearXNG | ~1 天 | 低 | Docker 或单体；`search_gateway` 接入 |
| 4 | **PE-C-2** | OpenObserve | ~2 天 | 无 | 日志 shipper；与 `observability/` 对齐 |
| 5 | **PE-F-1** | ThingsBoard CE + Ditto | ~2 天（**参考**） | 无 | 文档 + ADR；不改 Device Gateway 热路径 |

```text
PE-C-1 Netdata MCP          ← 立刻增强 VPS 自诊断
    ↓
PE-B-1 codesearch MCP       ← LiMa 代码理解
    ↓
PE-D-1 SearXNG              ← research grounding
    ↓
PE-C-2 OpenObserve          ← 历史日志/trace 观察台
    ↓
PE-F-1 ThingsBoard/Ditto    ← Device Gateway 后续台账/孪生参考
```

**并行可开（不挡第一批）：**

- **PE-A-1** MCP registry inventory 脚本（零路由，可与 PE-C-1 并行）
- **PE-B-2** searchcode MCP 评估（只读公开代码）

**明确后置：**

- **Kestra**（PE-E-1）— 等 OpenObserve + 现有 smoke 脚本清单稳定
- **Uptime Kuma**（PE-E-2）— 可选；INF-B Healthchecks 已代码完成
- **SigNoz** — 仅当 OpenObserve 不满足 trace 需求时再评

---

## 5. Phase 任务分解

### PE-C-1 — Netdata MCP（P0，~1 天）

| Task | 内容 |
|------|------|
| C-1.1 | VPS 安装 Netdata Agent（或 Parent+Child）；document port/firewall |
| C-1.2 | 启用 Netdata MCP endpoint；只读 tool allowlist |
| C-1.3 | `docs/NETDATA_MCP_RUNBOOK.md` — Operator + Agent 查询示例 |
| C-1.4 | `scripts/smoke_netdata_mcp_vps.py` — CPU/mem/disk 可读 |
| C-1.5 | 可选：LiMa MCP connector 条目 `candidate` |

**验收：** Agent 通过 MCP 查询 VPS 指标；`progress.md` 有 smoke 证据；**不改** LiMa 路由。

---

### PE-B-1 — codesearch MCP（P0，~1–2 天）

| Task | 内容 |
|------|------|
| B-1.1 | 调研 codesearch MCP 部署（Rust binary / Docker） |
| B-1.2 | `docs/CODESEARCH_MCP_SETUP.md` — 索引 `D:\GIT` + 参考仓 allowlist |
| B-1.3 | LiMa MCP 注册 read-only `codesearch_query`（或官方 tool 名映射） |
| B-1.4 | 对比 baseline：`rg` vs codesearch 延迟与召回（3 条 fixture query） |

**验收：** LiMa 任务可语义查本地仓；私有路径不在 allowlist 则拒绝。

---

### PE-D-1 — SearXNG（P1，~1 天）

| Task | 内容 |
|------|------|
| D-1.1 | Docker Compose 或 VPS 单体部署 SearXNG |
| D-1.2 | `search_gateway/searxng_adapter.py` — 缓存 TTL、冷却、来源标注 |
| D-1.3 | env：`SEARXNG_ENABLED=0`、`SEARXNG_BASE_URL` |
| D-1.4 | 接入 dev-search / research 路径（**非**默认 chat 路由） |
| D-1.5 | `docs/SEARXNG_SETUP.md` |

**验收：** 启用后 research 查询返回带 source URL；限流时 graceful fallback 到百度/TinyFish。

---

### PE-C-2 — OpenObserve（P1，~2 天）

| Task | 内容 |
|------|------|
| C-2.1 | 选型记录：OpenObserve vs SigNoz（本计划默认 OpenObserve） |
| C-2.2 | VPS 单体部署；保留 `/opt/lima-router` journal 备份路径 |
| C-2.3 | ship `lima-router` systemd logs + 可选 `observability/events` export |
| C-2.4 | `docs/OPENOBSERVE_SETUP.md` — 按 request_id / task_id 查询 |
| C-2.5 | Operator runbook：FRP down、Redis OOM、DG WSS 断连 三类场景 |

**验收：** 可翻 24h 历史错误；与 Telegram digest 不重复（digest 摘要，OpenObserve 明细）。

---

### PE-F-1 — ThingsBoard CE + Ditto 参考（P1，~2 天，文档为主）

| Task | 内容 |
|------|------|
| F-1.1 | `docs/reference/DEVICE_PLATFORM_REFERENCE.md` — TB CE vs Ditto vs LiMa DG 对照 |
| F-1.2 | Ditto 状态模型草图：device `desired` / `reported` / `policy` 映射到现有 task/event |
| F-1.3 | ESPHome：fake-u8 传感器样机选项（可选 compose，默认关） |
| F-1.4 | ADR：是否/何时引入外部 CMDB — **默认否，仅借鉴** |

**验收：** 文档 + ADR；**无** Device Gateway 生产路径改动。

---

### PE-A-1 — MCP Registry Inventory（P1，~4h，可并行）

| Task | 内容 |
|------|------|
| A-1.1 | `scripts/inventory_mcp_registries.py` — Glama + Official Registry + SafeMCP |
| A-1.2 | 去重、打标签（coding/ops/search/browser/data） |
| A-1.3 | 输出 `data/mcp_registry_snapshot.json` + 更新 `MCP_CONNECTOR_CATALOG.md` candidate 区 |
| A-1.4 | weekly cron 或 Kestra 占位（PE-E 后再接） |

**验收：** 脚本 dry-run OK；catalog 新增 ≥1 条有来源 URL 的 candidate。

---

## 6. 文件与模块（预期）

```text
scripts/
  inventory_mcp_registries.py      # PE-A-1
  smoke_netdata_mcp_vps.py         # PE-C-1
  smoke_searxng_local.py           # PE-D-1

search_gateway/
  searxng_adapter.py               # PE-D-1

docs/
  NETDATA_MCP_RUNBOOK.md
  CODESEARCH_MCP_SETUP.md
  SEARXNG_SETUP.md
  OPENOBSERVE_SETUP.md
  reference/DEVICE_PLATFORM_REFERENCE.md

data/
  mcp_registry_snapshot.json       # PE-A-1

docs/reference/
  MCP_CONNECTOR_CATALOG.md         # candidate 区持续更新
```

---

## 7. 环境变量（汇总，均默认关）

```bash
# PE-D SearXNG
SEARXNG_ENABLED=0
SEARXNG_BASE_URL=http://127.0.0.1:8080
SEARXNG_CACHE_TTL_SEC=300
SEARXNG_COOLDOWN_SEC=2

# PE-C OpenObserve
OPENOBSERVE_ENABLED=0
OPENOBSERVE_URL=
OPENOBSERVE_ORG=default

# PE-C Netdata（通常无 secret；MCP 若需 token 仅 VPS .env）
NETDATA_MCP_URL=http://127.0.0.1:19999/mcp

# PE-B codesearch
CODESEARCH_MCP_ENABLED=0
CODESEARCH_INDEX_PATHS=D:/GIT,D:/GIT/deepcode-cli
```

---

## 8. 与现有计划的关系

| 现有计划 | 关系 |
|----------|------|
| `infra-tools-integration` INF-A/B/C | Infisical/Healthchecks/Tailscale **并行**；Uptime Kuma 可选替 INF-B SaaS |
| `telegram-github-maximization` | Telegram 仍是告警通道；Kestra 编排 digest/smoke 事件 |
| `lima-dev-search-tools` | dev-search 为 LiMa-owned 默认；SearXNG/searchcode/codesearch 为 **增强 tier** |
| `gitee/cloudflare-maximization` | PE-A free tier 雷达 **扩展现有** inventory 脚本模式 |
| `provider-model-automation` | **仍暂停**；本计划优先生产力六能力 |
| `productivity-infrastructure-review` PROD-006~011 | PE-C/PE-F **直接回应** observability 与 visualization 缺口 |

---

## 9. 验收总清单

- [ ] `docs/superpowers/plans/2026-05-26-lima-productivity-enhancement.md`（本文件）
- [ ] PE-C-1 Netdata MCP VPS smoke
- [ ] PE-B-1 codesearch MCP 本地查询 smoke
- [ ] PE-D-1 SearXNG adapter + fallback
- [ ] PE-C-2 OpenObserve 24h 日志可查
- [ ] PE-F-1 Device 平台参考文档 + ADR
- [ ] PE-A-1 MCP registry inventory + catalog 更新
- [ ] `.env.example` 同步 key 名（无真实值）
- [ ] `progress.md` / `findings.md` closeout；pytest 不退化

---

## 10. 参考链接

| 资源 | URL |
|------|-----|
| Glama MCP | https://glama.ai/mcp/servers |
| Official MCP Registry | https://registry.modelcontextprotocol.io/ |
| SafeMCP | https://safemcp.com/ |
| SearXNG | https://docs.searxng.org/ |
| OpenObserve | https://openobserve.ai/docs/ |
| Netdata | https://www.netdata.cloud/ |
| Kestra | https://kestra.io/ |
| ThingsBoard CE | https://thingsboard.io/docs/ |
| Eclipse Ditto | https://www.eclipse.org/ditto/ |
| ESPHome | https://esphome.io/ |

---

## 11. 下一刀建议

**立即开 PE-C-1（Netdata MCP）** — 零路由风险、直接改善 VPS/FRP/Redis 排障闭环；可与 **PE-A-1** MCP inventory 并行。

Chat 模型扩容（CF-G-3、GI-G-3 overlay）降为 **P2**，待 **五线 closeout**（`2026-05-26-five-line-closeout.md`）≥80% 后再排期。
