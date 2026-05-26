# 五线 Closeout 路线图 — Telegram · GitHub · Gitee · CF · Google

> **Status:** Active execution order | **Created:** 2026-05-26
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
| | TG-GH-2 LiMa Code 推送 | ✅ 文档 + submodule | E2E 手工 smoke |
| | TG-GH-3 统一早报 | ✅ | — |
| | TG-GH-4 `/github` `/device` | ✅ | — |
| | TG-GH-5 事件加深 | ✅ | — |
| | TG-GH-6 deploy/smoke 推送 | ❌ | — |
| **GitHub** | CQ-GH-001 webhook | ✅ | — |
| | TG-GH-5 issues/release/PR | ✅ | — |
| **Gitee** | GI-G-0/1 镜像 | ✅ | — |
| | GI-G-2 webhook→TG | ✅ | UI secret 对齐 |
| | GI-G-3 模力方舟 AI | ⏸ 基础设施 | **resource_not_bound** |
| | GI-G-5 digest + mirror lag | ✅ | — |
| **Cloudflare** | CF-G-0/1/2 | ✅ | — |
| | CF-G-3 路由 | ✅ | — |
| | CF-G-6 inventory diff | ❌ | — |
| **Google** | CF-G-0 inventory | ✅ | — |
| | CF-G-1 budget | ✅ | — |
| | CF-G-3 路由优化 | ✅ | VPS 待 chat_fast 命中证据 |

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
| 7 | **GI-G-3** | Gitee 控制台绑定资源包 → re-probe | 运维 | 用户操作 |

**并行：** GI-G-2 真实 push 验证（双 push 去重）；TG-GH-2 Windows E2E。

---

## 4. 验收总清单

- [ ] `chat_fast` 请求日志可见 `google_flash_lite` 命中
- [ ] vision fallback 含 `cf_vision` → `google_flash`
- [ ] Telegram `/github psf/requests README.md` 返回摘要
- [ ] Telegram `/device status` 返回 health + task 摘要
- [ ] `gitee_mirror_lag_check.py` 输出 SHA 一致/漂移
- [ ] TG-GH-5 test issue → Telegram
- [ ] deploy smoke → Telegram（TG-GH-6）
- [ ] `progress.md` / `findings.md` 每刀 closeout

---

## 5. 与生产力计划关系

[`2026-05-26-lima-productivity-enhancement.md`](2026-05-26-lima-productivity-enhancement.md) **暂停排期**，待本文件 §4 验收 ≥80% 后再启 **PE-C-1 Netdata MCP**。
