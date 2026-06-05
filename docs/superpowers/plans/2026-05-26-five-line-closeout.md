# 五线 Closeout 路线图 — Telegram · GitHub · Gitee · CF · Google

> **Status:** P0 closeout **~95%** | **Created:** 2026-05-26 | **Re-acceptance:** 2026-05-26 12:45+ `acceptance_ok` sha=`22e7b4f`
>
> **Supersedes for scheduling:** `docs/superpowers/plans/2026-05-26-lima-productivity-enhancement.md`（Netdata/SearXNG 等 **后置**）
>
> **Related plans:**
> - [`2026-05-26-telegram-github-maximization.md`](2026-05-26-telegram-github-maximization.md)
> - [`2026-05-26-gitee-maximization.md`](2026-05-26-gitee-maximization.md)
> - [`2026-05-26-cloudflare-google-maximization.md`](2026-05-26-cloudflare-google-maximization.md)

---

## 1. 总原则

LiMa 当前优先 **Operator 通道 + 免费 API 额度 + 国内镜像**，而不是再接聊天模型或 Netdata/SearXNG 等生产力基建。

```text
P0  closeout（本文件）
  Telegram TG-GH-4~6
  GitHub  TG-GH-5
  Gitee   GI-G-5（GI-G-3 待资源包）
  CF      CF-G-3 + CF-G-6 余量
  Google  CF-G-3 路由 + inventory diff

P2  延后
  PE-* 生产力六能力（Netdata、SearXNG、OpenObserve…）
  GI-G-3 overlay（resource_not_bound）
  GI-G-4 / CF-G-5 Pages 官网
```

---

## 2. 现状矩阵（2026-05-26）

| 线 | Phase | 状态 | 阻塞 |
|----|-------|------|------|
| **Telegram** | TG-GH-1 出站可靠 | ✅ | — |
| | TG-GH-2 LiMa 推送 | ✅ 文档 + submodule | E2E 手工 smoke |
| | TG-GH-3 统一早报 | ✅ | — |
| | TG-GH-4 `/github` `/device` | ✅ | — |
| | TG-GH-5 事件加深 | ✅ | — |
| | TG-GH-6 deploy/smoke 推送 | ✅ | `LIMA_DEPLOY_NOTIFY=0` 可关 |
| **GitHub** | CQ-GH-001 webhook | ✅ | — |
| | TG-GH-5 issues/release/PR | ✅ | — |
| | GH-PUSH-MSG commit 摘要 | ✅ | 手机 12:41 `22e7b4f` 含 message + 【译】 |
| **Gitee** | GI-G-0/1 镜像 | ✅ | mirror_lag sha=`22e7b4f` |
| | GI-G-2 webhook→TG | ✅ | 手机 12:41 双推同 SHA；acceptance 200 |
| | GI-G-3 模力方舟 AI | ❌ Cancelled | 无免费资源包 |
| | GI-G-5 digest + mirror lag | ✅ | — |
| **Cloudflare** | CF-G-0/1/2 | ✅ | — |
| | CF-G-3 路由 | ✅ | — |
| | CF-G-6 inventory diff | ✅ | Google fetch VPS 网络偶发失败 |
| **Google** | CF-G-0 inventory | ✅ | — |
| | CF-G-1 budget | ✅ | — |
| | CF-G-3 路由优化 | ✅ | acceptance: `chat_fast google_flash_lite` |

**仍 Open（不挡 Operator 闭环）：** GI-G-3 模力方舟 AI（blocked）；CF-G-6 Google inventory VPS 偶发 unreachable；TG-GH-2 LiMa→TG E2E 手工。

---

## 3. 推荐执行顺序

| 序 | ID | 内容 | 估时 | 依赖 |
|----|-----|------|------|------|
| 1 | **CF-G-3** | `google_flash_lite` → `chat_fast.strong`；`cf_vision`/`google_flash` → vision 链 | 4h | 无 |
| 2 | **TG-GH-4** | Telegram `/github` + `/device status` | 1d | TG-GH-1 ✅ |
| 3 | **GI-G-5** | mirror lag 脚本 + digest 已含 Gitee 24h（验证） | 3h | TG-GH-3 ✅ |
| 4 | **TG-GH-5** | GitHub issues/release/workflow 扩展 | 1d | webhook 基线 ✅ |
| 5 | **TG-GH-6** | `deploy_*.py` / smoke 成功 → Telegram | 4h | TG-GH-1 ✅ |
| 6 | **CF-G-6** | weekly inventory diff → Telegram | 4h | CF-G-0 + TG-GH-3 ✅ |
| 7 | **GI-G-3** | Gitee 控制台绑定资源包 → re-probe | 运维 | 用户操作 — **2026-05-26 仍 blocked** |

**并行（2026-05-26 已跑）：** GI-G-2 Gitee webhook public smoke ✅；§4 `smoke_five_line_acceptance.py` ✅（复跑：mirror_lag + routing + github_issue + gitee **acceptance_ok**）

**P0 收齐判定：** Operator 通知链（GitHub/Gitee→Telegram+翻译+commit 摘要）+ CF/Google 路由 + 镜像 lag **已闭环**；GI-G-3 与 Google inventory VPS 稳定性 **除外**。

**P0 收齐后：** 可正式切换 `docs/NEXT_MILESTONES.md` 四线主线；PE 六能力维持 P2。

---

## 4. 验收总清单

- [x] `chat_fast` VPS 配置首位 `google_flash_lite`（routing smoke）
- [x] vision fallback 含 `cf_vision` → `google_flash`（routing smoke）
- [x] Telegram `/github` `/device` 手机手工（FL-1-7，2026-05-26 11:05）
- [x] `gitee_mirror_lag_check.py` SHA 一致（2026-05-26 复跑 `22e7b4f`）
- [x] TG-GH-5 test issue → webhook 200（acceptance smoke）
- [x] deploy smoke → Telegram（TG-GH-6）
- [x] weekly inventory diff → Telegram digest（CF-G-6）
- [x] GitHub/Gitee push Telegram 含 commit message（GH-PUSH-MSG，手机 12:41）
- [x] `smoke_five_line_acceptance.py` 复跑 **acceptance_ok**（2026-05-26）
- [x] `progress.md` / `findings.md` GH-PUSH-MSG + 五线 re-acceptance closeout

---

## 5. 与生产力计划关系

[`2026-05-26-lima-productivity-enhancement.md`](2026-05-26-lima-productivity-enhancement.md) **维持 P2**；§4 已 ≥95%，下一执行入口见 [`docs/NEXT_MILESTONES.md`](../NEXT_MILESTONES.md) 四线地图。
