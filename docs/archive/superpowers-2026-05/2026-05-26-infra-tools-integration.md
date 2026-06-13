# 基础设施工具接入 — Infisical / Healthchecks / Tailscale

> **For agentic workers:** 文档先行；**零路由改动**；新网络/密钥能力 **默认关**，VPS smoke 后再启用。
>
> **Goal:** 补 LiMa 当前最短板——密钥分散、定时任务 dead-man、多端私有联调——而不引入第二套 eval/trace 平台。
>
> **Status:** Active plan | **Created:** 2026-05-26
>
> **Related:** `docs/LOCAL_PROXY_RUNTIME_STATUS.md`、`infra/README.md`、`docs/OBSERVABILITY_EVENTS.md`、
> （已退役）Telegram/GitHub 告警通道、
> `AGENTS.md`（禁止提交真实密钥）

---

## 1. 战略定位

```text
LiMa 运维层（本计划）
  ├── 密钥：Infisical（Cloud Free + CLI inject）→ 替代散落 .env / 手工 VPS 粘贴
  ├── 存活：Healthchecks.io dead-man → 补 Telegram「跑了但失败」之外的「根本没跑」
  └── 联调：Tailscale mesh → VPS ↔ Windows 私有 smoke，逐步减 FRP 调试依赖

暂缓（单独计划，本文件不实施）
  ├── OpenLLMetry / Opik（路由 trace UI）
  ├── SearXNG / Meilisearch / Unstructured（检索/RAG）
  └── Inspect AI / Evidently（离线 eval 报告）
```

**原则：**

1. **不修改** `routing_engine` / `router_v3` / `backends_registry.py` 路由逻辑。
2. **不提交** 真实密钥；Infisical 只存 secret，仓库只留 `.env.example` + 文档。
3. **可回滚**：任一阶段失败 → 恢复本地 `.env` + systemd 原样；Tailscale 可卸载不影响公网 HTTPS。
4. **默认关**：`LIMA_INFISICAL_ENABLED=0`、`LIMA_TAILSCALE_SMOKE=0` 直到 smoke 证据写入 `progress.md`。
5. **单操作员**：Personal Free 档位足够；不自托管 Infisical/Tailscale control plane。

---

## 2. 现状审计（2026-05-26）

| 能力 | 已有 | 缺口 |
|------|------|------|
| 密钥存储 | VPS `/opt/lima-router/.env`、本地 `D:\GIT\.env`、frpc 本地配置 | 多副本漂移；无 central audit；pre-commit 仅本地 scan |
| 健康检查 | `infra/lima-health.bat`（Windows 每 5min）、Telegram `/health` | **无** cron 未执行告警；VPS probe 脚本无 dead-man |
| 多端联调 | FRP `8088→8080`、公网 HTTPS | FRP 脆弱、Windows 必须在线；ESP32 仍走公网 Device Gateway |
| 告警 | Telegram bot、GitHub Webhook | 适合事件驱动，不适合「定时任务沉默」 |
| Trace/eval | `observability/`、`eval_registry`、pytest eval | 够用；Opik/OpenLLMetry **不在本阶段** |

**Pain evidence：**

- `docs/LOCAL_PROXY_RUNTIME_STATUS.md` — FRP 路径依赖 Windows `8080` 常挂。
- CF-G-2 VPS deploy — `backends_registry.py` 在 VPS 不存在，`.env` 与代码分离。
- `AGENTS.md` — Agent 可部署 VPS 但不得泄露密钥。

---

## 3. 优先级与阶段

| Phase | 工具 | 估时 | 路由风险 | 依赖 |
|-------|------|------|----------|------|
| **INF-A** | Infisical 密钥集中 + scan | ~4h | 无 | 账号注册 |
| **INF-B** | Healthchecks.io dead-man | ~2h | 无 | INF-A 可选 |
| **INF-C** | Tailscale VPS↔Windows | ~4h | 低（并行路径） | INF-A（TS auth key 进 Infisical） |
| INF-D | OpenLLMetry（后续） | ~6h | 无 | 本计划 closeout 后 |

**建议执行顺序：** INF-A → INF-B → INF-C（与 TG-GH / CF-G 并行，不阻塞）。

---

## 4. Phase INF-A — Infisical

### 4.1 目标

- 单一 source of truth：`lima-router-prod`、`lima-windows-dev`、`lima-ci` 三个 Environment/Project（或单 Project 多 env）。
- VPS `systemd` 与本地开发通过 **CLI inject**，不再 SSH 手工 `sed .env`。
- CI / pre-commit：secret scanning 对接 Infisical 或保留现有 scan + Infisical audit log。

### 4.2 密钥清单（首批迁入，勿写入本仓库）

| Secret | 消费方 |
|--------|--------|
| `CLOUDFLARE_ACCOUNT_ID` / `CLOUDFLARE_TOKEN` | VPS router |
| `GOOGLE_AI_KEY` | VPS router |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` / `TELEGRAM_WEBHOOK_SECRET` | VPS |
| `GITHUB_WEBHOOK_SECRET` | VPS |
| `LIMA_ADMIN_TOKEN` | VPS / LiMa Code |
| `GFW_PROXY` / frpc 相关 | Windows only |
| Tailscale auth key（INF-C） | VPS + Windows |

**保留本地不入库：** 仅机器级路径、非 secret 的 `LIMA_DYNAMIC_ADMISSION=1` 等 flag 可留 `.env` 明文。

### 4.3 任务

| Task | 产出 |
|------|------|
| A.1 | Infisical Cloud 项目创建；邀请仅 owner |
| A.2 | `docs/INFISICAL_SETUP.md` — 登录、CLI、`infisical run` 示例 |
| A.3 | `scripts/infisical_pull_env.example.sh` — VPS 拉取模板（**不含真实值**） |
| A.4 | VPS：`/etc/systemd/system/lima-router.service.d/infisical.conf` 或 wrapper `ExecStart=/usr/bin/infisical run -- …` |
| A.5 | Windows：Task Scheduler 启动脚本改为 `infisical run -- python server.py`（本地 dev 可选） |
| A.6 | `.env.example` 同步 key 名；`tests/test_secret_hygiene.py` 仍 pass |

### 4.4 验收

- [ ] VPS restart 后 `/health` 200，CF smoke 仍通（不降级路由）
- [ ] 仓库 `git grep` 无新增 `sk-` / `gho_` / 真实 token
- [ ] 回滚：去掉 infisical wrapper，恢复纯 `.env` 文件启动

---

## 5. Phase INF-B — Healthchecks.io

### 5.1 目标

**Dead-man switch：** 预期周期内未收到 ping → 邮件/Telegram（Healthchecks 自带或 webhook 到现有 bot）。

### 5.2 首批 Check（Personal Free 足够）

| Check 名 | 周期 | 执行体 | Ping 时机 |
|----------|------|--------|-----------|
| `lima-vps-router` | 5 min | VPS cron | `curl -sf localhost:8080/health` 成功后 |
| `lima-vps-probe-weekly` | 7 d | VPS timer | `probe_cf_new_models.py --limit 5` 完成后（仅 ping，不必 apply） |
| `lima-windows-router` | 5 min | Task Scheduler 追加 | 本地 `8080/health` 成功后 |
| `lima-frpc-tunnel` | 5 min | `lima-health.bat` 末尾 | frpc 进程存在且 VPS→8088 smoke 可选 |

### 5.3 任务

| Task | 产出 | 状态 |
|------|------|------|
| B.1 | Healthchecks.io 账号 + 4 个 check UUID | 待运维 |
| B.2 | `scripts/healthcheck_ping.sh` + `.ps1` + `healthcheck_ping.py` | ✅ |
| B.3 | UUID 存 env（示例 `.env.example`） | ✅ |
| B.4 | `scripts/vps_router_healthcheck.sh` + `docs/HEALTHCHECKS_SETUP.md` | ✅ |
| B.5 | `infra/lima-health.bat` 可选 ping | ✅ |
| B.6 | 可选 Healthchecks webhook → Telegram | 后续 |

### 5.4 与 Telegram 分工

| 场景 | Healthchecks | Telegram |
|------|--------------|----------|
| cron 未跑 | ✅ | ❌ |
| smoke 失败但进程跑了 | ❌（除非脚本内主动 alert） | ✅ |
| GitHub push / budget 80% | ❌ | ✅ |

### 5.5 验收

- [ ] 故意停 `lima-router` 10min → Healthchecks 告警收到
- [ ] 恢复服务 → 下一 ping 后 check 变绿
- [ ] 不影响现有 Telegram webhook / digest

---

## 6. Phase INF-C — Tailscale（Personal Free）

### 6.1 目标

- VPS 与 Windows 加入同一 tailnet，**私有**访问 LiMa API / 本地 proxy smoke。
- 减少「FRP 断了但不知道」的调试时间；**不替换** 公网 `chat.donglicao.com` 用户入口（Phase 1）。

### 6.2 范围（Phase C1，最小切片）

| 节点 | 角色 | 验证 |
|------|------|------|
| VPS `47.112.162.80` | tailscale + 可选 `--advertise-tags=tag:lima` | `tailscale status` |
| Windows dev | tailscale | 从 Windows ping VPS tailscale IP:8080 |
| ESP32 / Device Gateway | **不在 C1** | 仍公网 HTTPS + token；C2 再评估 subnet router |

### 6.3 任务

| Task | 产出 |
|------|------|
| C.1 | Tailscale 账号；ACL 默认 deny，仅 owner 设备互访 |
| C.2 | VPS：`tailscale up --authkey=… --hostname=lima-vps` |
| C.3 | Windows：`tailscale up --hostname=lima-win` |
| C.4 | `docs/TAILSCALE_LIMA_SMOKE.md` — 私有 URL 示例 `http://100.x.x.x:8080/health` |
| C.5 | `scripts/smoke_tailscale_router.py` — Windows → VPS tailscale IP health + 1 chat |
| C.6 | FRP **保留**；文档注明「公网 IDE 仍走 HTTPS，Tailscale 仅运维/联调」 |

### 6.4 验收

- [ ] Windows → VPS tailscale IP `/health` 200（不经公网 IP）
- [ ] 公网 `chat.donglicao.com` smoke 不退化
- [ ] `tailscale down` 可回滚，FRP 仍可用

---

## 7. 文件与目录（计划新增）

```text
docs/INFISICAL_SETUP.md              # INF-A 操作手册
docs/TAILSCALE_LIMA_SMOKE.md         # INF-C smoke 证据模板
scripts/healthcheck_ping.sh          # INF-B
scripts/healthcheck_ping.ps1         # INF-B
scripts/smoke_tailscale_router.py    # INF-C
scripts/infisical_pull_env.example.sh
.env.example                         # 仅 key 名 + HEALTHCHECK_* URL 占位
```

**不新增：** 路由模块、数据库、自托管 Infisical/Tailscale controller。

---

## 8. 环境变量（汇总，仅名称）

```bash
# Infisical
LIMA_INFISICAL_ENABLED=0          # 1 启用 inject
INFISICAL_TOKEN=                  # 机器级，Infisical 控制台生成
INFISICAL_PROJECT_ID=
INFISICAL_ENV=prod                # prod | dev

# Healthchecks（UUID 在 URL 路径中，整 URL 存 Infisical）
HEALTHCHECK_LIMA_VPS_URL=
HEALTHCHECK_LIMA_WINDOWS_URL=
HEALTHCHECK_FRPC_URL=

# Tailscale（C 阶段）
LIMA_TAILSCALE_SMOKE=0            # 1 启用私有 smoke 脚本
```

---

## 9. 与现有里程碑关系

```text
并行（不阻塞）:
  TG-GH-1/2     Telegram 可靠性 + LiMa Code 推送
  CF-G-3        Google 路由优化
  INF-A/B/C     本计划（密钥 / dead-man / mesh）

后续（单独计划）:
  INF-D         OpenLLMetry → routing_engine span
  INF-E         SearXNG → LiMa Code research
```

**建议第一刀：** INF-B Healthchecks（2h，零密钥迁移风险）或 INF-A（若你已准备好 Infisical 账号）。

---

## 10. 验收总清单

- [ ] Infisical：VPS + Windows 密钥从 central store inject；git 无新 secret
- [ ] Healthchecks：4 个 check 绿；停服实验告警可达
- [ ] Tailscale：VPS↔Windows 私有 `/health` smoke；公网路径不退化
- [ ] 文档 + `progress.md` / `findings.md` 证据
- [ ] 全量 pytest 不退化（本计划 **不应** 改生产 Python 路由路径；脚本/文档为主）

---

## 11. 参考

| 文档 | 用途 |
|------|------|
| [Infisical Docs](https://infisical.com/docs) | CLI、`infisical run`、secret scanning |
| [Healthchecks.io Docs](https://healthchecks.io/docs/) | Ping URL、grace、integrations |
| [Tailscale KB](https://tailscale.com/kb/) | Personal plan、ACL、subnet router（C2） |
| `docs/ONLINE_DISTRIBUTIONS.md` | 公网入口权威 |
| `docs/OBSERVABILITY_EVENTS.md` | 本地 observability 边界（不与 INF-D 重复） |
