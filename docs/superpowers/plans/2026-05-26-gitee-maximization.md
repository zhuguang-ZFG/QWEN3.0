# Gitee 利用最大化 — 详细实施方案

> **For agentic workers:** 文档先行；**默认关**；复用 CQ-GH-001 / TG-GH 模式，不重复造轮子。
>
> **Goal:** 把 Gitee 变成 LiMa 的 **国内代码镜像 + 事件源 + 可选 AI 后端**，与 GitHub 双轨并行，Telegram 统一出口。
>
> **Status:** Active plan | **Created:** 2026-05-26
>
> **Related:** [`2026-05-26-telegram-github-maximization.md`](2026-05-26-telegram-github-maximization.md)、
> [`2026-05-26-cloudflare-google-maximization.md`](2026-05-26-cloudflare-google-maximization.md)（CF-G-5 官网）、
> `docs/GITHUB_WEBHOOK_INTEGRATION.md`、`docs/LIMACODE_MANAGEMENT.md`

---

## 1. 战略定位

```text
LiMa 代码与事件（双托管）
  ├── GitHub（主）     push/PR/CI → /github/webhook → Telegram  ✅ CQ-GH-001
  └── Gitee（国内镜）  push/PR/流水线 → /gitee/webhook → Telegram  ← 本计划 GI-G-2

LiMa 推理池（可选第三轨）
  ├── L0  SCNet / 本地
  ├── L1  Cloudflare / Google / GitHub Models
  └── L2  模力方舟 ai.gitee.com（OpenAI 兼容）← GI-G-3，floor/medium only

LiMa 静态站点（国内访问）
  ├── VPS nginx（现状）
  ├── CF Pages（CF-G-5）
  └── Gitee Pages（GI-G-4，国内备选）
```

**原则：**

1. **GitHub 仍是主仓**；Gitee 是镜像与国内可达性，不替代 submodule 治理与 LiMa Code 契约。
2. **默认关**：`GITEE_WEBHOOK_ENABLED=0`、`GITEE_AI_ENABLED=0` 直到 smoke 证据写入 `progress.md`。
3. **不自动** `git pull`、merge、开 PR；事件只推 Telegram 摘要（与 GitHub 一致）。
4. **新 AI 模型** 先 inventory → smoke → budget → **late_fallback**，不进 coding 第一梯队。
5. **零路由风险切片优先**：GI-G-0/1/2 不改 `router_v3` 主路径。

**不做：**

- Gitee 当 LiMa 主数据库或 Agent 任务存储。
- 未 smoke 的模力方舟模型自动进 `code_orchestrator` 主池。
- 与 GitHub webhook 重复推送同一 commit 的两份摘要（GI-G-2 含去重策略）。

---

## 2. 现状审计（2026-05-26）

| 能力 | 已有 | 缺口 |
|------|------|------|
| Git 双 remote push | 运维习惯（`origin` GitHub + Gitee remote） | 无文档化 runbook；无 push 失败告警 |
| Gitee Webhook → LiMa | 无 | 国内手机看不到 Gitee 上单独 push |
| 模力方舟 AI API | 无 `gitee_*` backend | `ai.gitee.com/v1/chat/completions` 未接入 |
| Gitee Pages | 未用 | 国内官网备选未评估 |
| Telegram 出口 | ✅ FRP 7897 | 与 TG-GH-1 共用可靠性 |
| 与 GitHub 事件去重 | 无 | 双 push 时可能 Telegram 双条 |

**参考 API / 文档：**

| 来源 | 用途 |
|------|------|
| [Gitee WebHook 数据格式](https://help.gitee.com/webhook/gitee-webhook-push-data-format) | push / MR 验签与 payload |
| [模力方舟 Serverless API](https://ai.gitee.com/docs/integrations/intro) | OpenAI 兼容 chat |
| [模力方舟异步任务 Webhook](https://ai.gitee.com/docs/products/apis/async-task) | 长任务回调（GI-G-3 后期） |

---

## 3. 利用最大化矩阵

| 资源 | 当前 | 目标 | 手段 |
|------|------|------|------|
| Gitee 仓库镜像 | 手动 push | **push 必达 + 失败可见** | GI-G-1 hook + Telegram |
| Gitee WebHook | 未接 LiMa | push/MR/流水线 fail → 手机 | GI-G-2 |
| 模力方舟免费/低价模型 | 0 | 1–3 个经 smoke 的 `gitee_*` floor | GI-G-3 |
| Gitee Pages | 0 | 国内静态站备选 | GI-G-4 |
| Operator 早报 | 仅 GitHub（计划 TG-GH-3） | GitHub + Gitee 24h 合并 | GI-G-5 |

---

## 4. 实施分片

### Phase GI-G-0 — 基线盘点（P0，~2h，零路由）

**目标：** 搞清楚「Gitee 侧已经有什么、缺什么」。

| Task | 产出 | 状态 |
|------|------|------|
| 0.1 | `docs/GITEE_BASELINE.md` | ✅ |
| 0.2 | `scripts/gitee_mirror_status.py` | ✅ |
| 0.3 | 模力方舟 token 状态（GI-G-3 前置） | 待账号 |
| 0.4 | 与 GitHub webhook 事件对比表 | ✅（见 baseline） |

**环境（勿提交）：**

```bash
GITEE_TOKEN=...          # 私人令牌，repo 读
GITEE_AI_TOKEN=...       # 模力方舟 Access Token（GI-G-3）
```

**验收：** 一份 baseline 文档 + 脚本 dry-run 不报错。

---

### Phase GI-G-1 — 镜像可靠性（P0，~3h）

**目标：** `git push github && git push gitee` 可观测、可恢复。

| Task | 内容 | 状态 |
|------|------|------|
| 1.1 | `docs/GITEE_MIRROR_RUNBOOK.md` | ✅ |
| 1.2 | `scripts/push_dual_remotes.py` / `.ps1` / `.sh` | ✅ |
| 1.3 | 可选 pre-push hook | 暂缓 |
| 1.4 | push 失败 → `notify_ops_event` | ✅（`--notify`） |

**验收：** 故意错误 remote URL → 脚本失败 + Telegram 收到（或日志明确）。

---

### Phase GI-G-2 — Gitee Webhook → Telegram（P0，~1 天）

**设计：** 镜像 CQ-GH-001 / `github_webhook/` 结构，独立模块便于测试。

| Task | 文件 |
|------|------|
| 2.1 | `gitee_webhook/verify.py` | ✅ |
| 2.2 | `gitee_webhook/format.py` | ✅ |
| 2.3 | `routes/gitee_webhook.py` | ✅ |
| 2.4 | nginx `/gitee/` + `patch_nginx_gitee_webhook.py` | ✅ |
| 2.5 | `notify_gitee_event()` | ✅ |
| 2.6 | `gitee_webhook/dedupe.py` + GitHub SHA record | ✅ |
| 2.7 | `tests/test_gitee_webhook.py` + smoke | ✅ |
| 2.8 | `docs/GITEE_WEBHOOK_INTEGRATION.md` | ✅ |

**环境变量：**

| 变量 | 说明 |
|------|------|
| `GITEE_WEBHOOK_ENABLED` | `1` 启用 |
| `GITEE_WEBHOOK_SECRET` | WebHook 密码或验签密钥 |
| `GITEE_WEBHOOK_REPOS` | 白名单 `owner/repo`，空=全部 |
| `GITEE_WEBHOOK_DEDUPE_GITHUB` | `1` 启用 SHA 去重（默认 `1`） |

**支持事件（首期）：**

| Gitee 事件 | 行为 |
|------------|------|
| Push Hook | 仓库、分支、commit 数、最新 SHA、推送者 |
| Merge Request Hook | open/merge/close 摘要 |
| Pipeline / CI fail | 仅失败推送（success 静默，对齐 GitHub workflow_run） |

**验收：**

- Gitee 仓库 WebHook 测试 delivery → VPS 200 → Telegram 一条
- 同一 commit 双 push GitHub+Gitee → Telegram **一条**（去重开）
- 未配置 secret → 403；`ENABLED=0` → 503

---

### Phase GI-G-3 — 模力方舟 AI 后端（P1，~1 天）

**目标：** 可选 `gitee_*` chat backend，国内线路补充 floor。

| Task | 内容 |
|------|------|
| 3.1 | `scripts/inventory_gitee_ai_models.py` — 列出可用模型 → `data/gitee_ai_inventory.json` | ✅ 247 / 89 chat |
| 3.2 | `provider_automation/adapters/gitee_ai.py` — OpenAI 兼容 smoke | ✅ |
| 3.3 | 1–3 个模型经 `ProbeRunner` → overlay | ⏸ 0 pass（resource_not_bound） |
| 3.4 | `budget_gitee.py` — 日限额 + digest | ✅ |
| 3.5 | `router_v3` — floor overlay only | ✅ admission provider |
| 3.6 | `GITEE_AI_ENABLED=0` 默认；token 仅 VPS `.env` | ✅ |

**Backend 命名：** `gitee_<model_slug>`，URL `https://ai.gitee.com/v1/chat/completions`。

**验收：** VPS smoke 1 个模型；budget 模拟 warn；`GITEE_AI_ENABLED=0` 时不路由。

---

### Phase GI-G-4 — Gitee Pages 国内官网（P2，~4h）

**与 CF-G-5 并列备选，二选一或并存。**

| 对比 | GitHub Pages | CF Pages | **Gitee Pages** |
|------|-------------|----------|-----------------|
| 国内访问 | 一般 | 较好 | **通常最好（大陆）** |
| 与 LiMa API | 跨域 | 跨域 / Worker 反代 | 同左 |
| 账号 | 分离 | CF 账号 | Gitee 账号 |

**步骤：** `donglicao-site/` → Gitee Pages → 自定义域 → demo 指向 `chat.donglicao.com/v1`。

**验收：** 国内 curl 首页 200；demo 对话 OK。

---

### Phase GI-G-5 — 与 TG-GH-3 早报合并（P1，~3h）

**依赖：** TG-GH-3 统一 digest 或 GI-G-2 activity buffer。

| Task | 内容 |
|------|------|
| 5.1 | `data/gitee_activity.json` ring buffer（或扩展现有 `github_activity.json` → `git_host_activity.json`） | ✅ `webhook_activity_buffer.py` |
| 5.2 | 早报段落：`Gitee 24h: N push, M MR` | ✅ TG-GH-3 |
| 5.3 | 每周 mirror lag 检查：GitHub vs Gitee 最新 commit SHA 是否一致 | ✅ `scripts/gitee_mirror_lag_check.py` |

**验收：** 手动触发 digest → 含 Gitee 行。

---

## 5. 优先级与依赖

```text
Week 1（可与 TG-GH-1 并行）:
  GI-G-0  baseline
  GI-G-1  双 remote push 可靠性

Week 2:
  GI-G-2  Webhook → Telegram（核心）
  GI-G-3  模力方舟 AI（可选，有 token 再做）

Week 3（可选）:
  GI-G-4  Gitee Pages
  GI-G-5  早报合并（依赖 TG-GH-3）
```

**相对其他计划：**

| 计划 | 关系 |
|------|------|
| TG-GH-1 | 共用 Telegram 出站；**应先于或并行** GI-G-2 |
| TG-GH-3 | GI-G-5 合并 digest |
| CF-G-5 | GI-G-4 二选一官网方案 |
| CF-G-3 | 无冲突；Google 与 Gitee AI 均为 floor |

**建议第一刀：** GI-G-0 baseline 文档 + `gitee_mirror_status.py`（零路由）。

---

## 6. 文件清单（预计）

```text
gitee_webhook/
  verify.py
  format.py
  dedupe.py

routes/
  gitee_webhook.py

provider_automation/adapters/
  gitee_ai.py                    # GI-G-3

scripts/
  gitee_mirror_status.py         # GI-G-0
  push_dual_remotes.ps1          # GI-G-1
  inventory_gitee_ai_models.py   # GI-G-3
  smoke_gitee_webhook_public.py  # GI-G-2

data/
  gitee_ai_inventory.json        # GI-G-3

docs/
  GITEE_BASELINE.md
  GITEE_MIRROR_RUNBOOK.md
  GITEE_WEBHOOK_INTEGRATION.md

tests/
  test_gitee_webhook.py
  test_gitee_ai_adapter.py       # GI-G-3
```

单文件 ≤300 行；验签与格式化分离（对齐 `github_webhook/`）。

---

## 7. 环境变量汇总

```bash
# Webhook（GI-G-2）
GITEE_WEBHOOK_ENABLED=0
GITEE_WEBHOOK_SECRET=
GITEE_WEBHOOK_REPOS=owner/lima-router,owner/deepcode-cli
GITEE_WEBHOOK_DEDUPE_GITHUB=1

# Git API（GI-G-0/1/5，可选）
GITEE_TOKEN=

# 模力方舟 AI（GI-G-3）
GITEE_AI_ENABLED=0
GITEE_AI_TOKEN=
GITEE_AI_BASE_URL=https://ai.gitee.com/v1
```

---

## 8. 安全与合规

| 风险 | 护栏 |
|------|------|
| Webhook 伪造 | `X-Gitee-Token` / 签名校验；repo 白名单 |
| 双 push 消息轰炸 | SHA 去重 + CI success 静默 |
| AI token 泄露 | 仅 VPS `.env`；redact 日志 |
| 镜像漂移 | GI-G-5 weekly SHA 对比告警 |
| 国内合规 | 模力方舟按平台 ToS；私有代码路径标记 data policy |

---

## 9. 验收总清单

- [ ] `docs/GITEE_BASELINE.md` 与 mirror runbook
- [ ] `POST /gitee/webhook` + Telegram smoke（GI-G-2）
- [ ] 双 push 去重 evidence
- [ ] 至少 1 个 `gitee_*` smoke（GI-G-3，可选）
- [ ] `.env.example` 同步 key 名（不含真实值）
- [ ] `progress.md` / `findings.md` closeout；pytest 不退化

---

## 10. 参考

| 文档 | 用途 |
|------|------|
| `docs/GITHUB_WEBHOOK_INTEGRATION.md` | 对称实现模板 |
| `docs/superpowers/plans/2026-05-26-telegram-github-maximization.md` | Telegram 主线 |
| [Gitee WebHook 帮助](https://help.gitee.com/webhook/gitee-webhook-push-data-format) | Payload / Header |
| [模力方舟集成指南](https://ai.gitee.com/docs/integrations/intro) | OpenAI 兼容 API |
