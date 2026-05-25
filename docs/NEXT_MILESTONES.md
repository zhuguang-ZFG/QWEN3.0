# LiMa 下一里程碑（四线并行）

> Updated: 2026-05-26
> 权威状态仍见 `STATUS.md`、`docs/EXECUTION_PLAN.md`、`findings.md`、`progress.md`。
> 本文件只做**优先级与文档对齐**；`docs/superpowers/plans/` 内未勾 checkbox 以状态文档为准。

## 文档清理说明（2026-05-26）

| 已过时表述 | 以何为准 |
|---|---|
| `task_plan.md`「继续拆 server / 合并 BACKENDS」 | `EXECUTION_PLAN` Phase 10、2026-05-24 Runtime Closure：**已关闭** |
| `PERSONAL_CODING_ASSISTANT_PLAN.md` Next Steps 1–3（检索/MCP） | `EXECUTION_PLAN` Phase 6–8：**已完成** |
| `findings.md` WX-089-4 / WX-088-4「Pending」 | CQ-090 已关闭；微信产品通道见 `WECHAT_RETIRED.md` |
| `STATUS.md` WeChat Channel 小节 smoke 路径 | 微信真机已退役；`/channel` 契约保留、`WECHAT_BRIDGE_ENABLED=0` |

---

## 优先级总览

| 顺序 | 条线 | 下一可交付切片 | 门禁 |
|:---:|---|---|---|
| P0 | 代码质量 | P0.1 chunked body 413；P0.2 `/api/live-key` 不泄钥 | 本地全量 pytest + 可选 VPS smoke |
| P1 | 编码后端 | Kimi/SCNet-large 经 Windows:8080 或 FRP:8088 重跑 eval；TheOldLLM 诊断 | 准入 JSON + 路由池不默认提升 |
| P1 | ESP32 / Device Gateway | PROD-003 真机烧录 + 真机运动 smoke | fake-U8 已通过；需硬件 |
| P2 | LiMa Code Worker | Prompt Contract v0.1 → Hooks v0.1 | bounded `/lima work` 已有；daemon 仍 gated |
| P3 | 横切 | Mastery admin UI；always-on daemon；Postgres 设备审计 | 各自独立批准 |

**已永久暂停（非 backlog）**：支付、公共注册、商业 billing、微信真机/机器人（`docs/WECHAT_RETIRED.md`）。

---

## 1. 编码后端

**现状（证据）**：SCNet 直连为第一梯队；Cloudflare Worker/direct 已接入；Kimi 本机 `4504` 常为 quota/需 refresh；page-only Web AI 仅 sandbox。

**下一切片（建议顺序）**

1. **本地代理 refresh + 重评** — `docs/FREE_MODEL_ROUTING_STATUS.md`、`scripts/eval_coding_backends.py`；经 `local_router_start.bat` → `8080` 或 VPS `8088`，勿用 VPS `localhost:4504/4505` 当健康信号。
2. **TheOldLLM 超时根因** — 记录到 `findings.md`，未过 eval 不进默认池。
3. **周期性重跑** — keys / rate limit / socket policy 变化后更新 `data/coding_backend_scores.json`。
4. **路由硬化（小）** — `health_tracker` + `probe_loop` 对 terminal-state 冷却；`/v1/models` 是否收紧私有边界（`task_plan` 风险项，未决产品决策）。

**完成定义**：候选有 eval JSON + `admission` 元数据 + 明确 tier 后才进 IDE 默认池。

---

## 2. LiMa Code Worker

**现状**：`/lima task|next|work`、审计、隔离、repo allowlist、VPS 真机 smoke `cfcd3f2b` → `needs_review`；**always-on daemon 未开**（故意 gated）。

**下一切片（建议顺序）**

1. **LiMa Task Prompt Contract v0.1** — `/agent/tasks`、worker prompt、role prompt、skill 提取统一 `Context/Task/Constraints/Verify/Output`（`task_plan.md` 第 4 项）。
2. **Hooks + Skill Auto-Activation v0.1** — `skill-rules.json` 风格、post-task/post-edit/stop 检查点、`.lima-code/dev/active/<task>/`（第 5 项；依赖 Contract）。
3. **Artifact → learning loop 接线验证** — PROD-008 已本地完成；补一条端到端证据（task → artifact → memory/routing candidate）。
4. **Owner 命令真接线（独立 slice）** — Channel `/code-task` 等仍为 stub；需 owner-auth + 审计（`findings.md` CQ-054 注记）。
5. **Always-on daemon** — 仅在人批准后：allowlist + budget + stop + audit + quarantine 全开。

**完成定义**：一条公开 HTTPS 任务可由 LiMa Code 自动跑完并提交，artifact 与 learning 证据可追溯。

---

## 3. ESP32 / Device Gateway

**现状**：公开 `https://chat.donglicao.com/device/v1/*`；Redis HA 任务队列 + session bus；P0.4/P0.5/P0.7 已部署；fake-U8 本地/公网 WSS 通过；**固件 compile 过，真机 flash/smoke pending**。

**下一切片（建议顺序）**

1. **PROD-003 真机** — 烧录 + 结构化失败事件 + `write`/`home` 真机 smoke（`STATUS.md` 残余风险）。
2. **esp32S_XYZ 子模块** — 按 `docs/ESP32S_XYZ_OPTIMIZATION_ROADMAP.md` 推进 PAUSE/RESUME/STOP/ESTOP 等架构缺口（与 LiMa 协议族对齐）。
3. **Postgres 审计库** — deferred；不阻塞实时 WSS；单独里程碑。
4. **M12 Hardware Companion** — `task_plan.md` Implementation Plan 唯一 **pending** 里程碑；与 Device Gateway 路线图对齐后再开。

**运维脚本**：`scripts/cleanup_wechat_vps.py`（微信残留）；设备 smoke 见 `scripts/smoke_online_distributions.py`。

---

## 4. 代码质量

**权威 backlog**：`docs/CODE_QUALITY_IMPROVEMENT_PLAN_2026-05-25.md`

| ID | 内容 | 状态 |
|---|---|---|
| P0.1 | ASGI 层 chunked body 上限 → 413 | 待做 |
| P0.2 | `/api/live-key` 不返回原始 `GOOGLE_AI_KEY` | 待做 |
| P0.3 | `deploy/key_rotation.py` 归档或鉴权加固 | 待做 |
| P1.1 | `semantic_cache.py` 写失败可观测 | 待做 |
| P1.2 | admin 登录常量时间比较 | 待做 |
| P1.3+ | 超 300 行：`routes/agent_tasks.py`、`code_orchestrator.py`、`session_memory/store.py`、`router_http.py` | 渐进拆分 |

**完成定义**：P0 三项有回归测试；全量 pytest 通过；`git diff --check` 干净。

---

## 验证命令（复用）

```powershell
python -m pytest -q tests/test_http_body_limit.py tests/test_channel_gateway_routes.py
python -m pytest -q --ignore=active_model
python scripts/smoke_online_distributions.py --api-key lima-local
python scripts/eval_coding_backends.py
```

---

## 相关文档索引

| 文档 | 用途 |
|---|---|
| `docs/EXECUTION_PLAN.md` | Phase 完成度与全局 Next Order |
| `docs/superpowers/PLAN_CLOSURE_STATUS.md` | Superpowers 计划开闭状态 |
| `docs/WECHAT_RETIRED.md` | 微信已放弃 |
| `docs/CODE_QUALITY_IMPROVEMENT_PLAN_2026-05-25.md` | 质量 P0/P1 |
| `docs/FREE_MODEL_ROUTING_STATUS.md` | 免费模型证据 |
| `docs/LIMACODE_MANAGEMENT.md` | LiMa Code 子模块 |
| `docs/ESP32S_XYZ_MANAGEMENT.md` | 硬件子模块 |
