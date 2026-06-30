# Cloudflare / GitHub / Google 利用率审计与优化建议

> 审计时间：2026-06-30
> 范围：LiMa 当前对 Cloudflare、GitHub、Google 免费/付费能力的使用情况，以及可落地的下一步优化。

---

## 1. 执行摘要

| 平台 | 当前利用 | 主要缺口 | 建议优先级 |
|---|---|---|---|
| **Cloudflare** | Pages（3 站点）、DNS、Zone 管理 | R2、Workers、Turnstile、AI Gateway、Analytics/RUM、Access | P1：Turnstile + npm/pnpm 构建缓存；P2：Workers 边缘路由 |
| **GitHub** | Actions（CI/CD/部署）、Dependabot、pip Actions Cache | npm/pnpm Actions Cache、Dependabot npm 覆盖、Dependabot alerts、Artifacts 保留策略 | P0：站点构建加 cache；P1：启用 Dependabot alerts |
| **Google** | Gemini/Gemma 后端在路由池 | Search Console、OAuth 登录、Analytics、Google AI 模型自动发现 | P2：Search Console / sitemap；P2：Google OAuth |
| **Telegram** | 已退役 | 不再新增 webhook / 出站通知（AGENTS.md 硬规则） | 禁止 |

---

## 2. Cloudflare

### 2.1 已使用

| 功能 | 用途 | 状态 |
|---|---|---|
| **Pages** | `lima-docs`、`lima-www`、`lima-chat-web` | ✅ 已部署并绑定自定义域名 |
| **DNS** | `docs`、`www`、`app`、`chat` CNAME | ✅ 已切到 Pages / Tunnel |
| **API 适配** | `backends_registry/cloudflare.py`、`provider_automation/adapters/cloudflare.py` | ✅ 14+ 直连模型、4 Worker 模型在池 |
| **预算管理** | `budget_cf_google.py`：CF 账户级 12000 neurons/天池 + 单后端限额 | ✅ 已配置 |

### 2.2 未使用 / 可优化

| 功能 | 价值 | 落地成本 | 建议 |
|---|---|---|---|
| **Cloudflare Turnstile** | 替换登录/注册页的简单验证码或隐藏验证，防机器人注册 | 低 | 在 `app.donglicao.com/register.html`/`login.html` 接入，服务端验证移到 `routes/client_keys.py` 或新增 `routes/turnstile.py` |
| **R2** | 存储 chat-web 大资源、设备日志、备份；比 Aliyun OSS 便宜且与 Pages 同账号 | 中 | 低优先级；当前静态站资源很小 |
| **Workers** | 边缘做 API 聚合、A/B 测试、地理围栏、chat-web 配置下发 | 中 | 可作为 Cloudflare Tunnel 替代或 fallback，但需架构评审 |
| **AI Gateway** | 统一 CF/GH/Google 模型调用入口，缓存、重试、配额观察 | 中 | 适合把 `cf_*` 和 `google_*` 流量先经过 Gateway，再路由到后端 |
| **Analytics / RUM** | 官网 Pages 性能、Core Web Vitals | 低 | 在 `donglicao-site-v2` 注入 Web Analytics/RUM snippet |
| **Cloudflare Access** | 保护 `/admin`、Prometheus、Qdrant 等内部入口 | 低 | 若已有内部域名可配，当前非阻塞 |

---

## 3. GitHub

### 3.1 已使用

| 功能 | 用途 | 状态 |
|---|---|---|
| **Actions Workflows** | `Tests`、`Deploy`、Pages 部署 ×3、`Setup Cloudflare Pages` | ✅ 活跃 |
| **Dependabot** | pip / docker / github-actions 每周检查 | ✅ 已配置 |
| **Actions Cache (pip)** | `Tests` 工作流缓存 `~/.cache/pip` | ✅ 已配置 |
| **Environment protection** | `Deploy` 使用 `environment: production` | ⚠️ 需要手动在 Settings → Environments 配置 reviewer |

### 3.2 最近 100 次运行统计

```text
Total: 100
Success: 77 | Failure: 18 | Cancelled: 5
Tests: 42 | Deploy: 36 | Deploy Next.js Site: 5 | Setup Cloudflare Pages: 5 | Deploy Docs Site: 4 | Deploy Chat Web: 3
```

> `Deploy` 失败在 2026-06-30 主要由 `/device/v1/health` 503 导致，已修复（JDCloud 设备 Redis 存储配置）。

### 3.3 未使用 / 可优化

| 功能 | 价值 | 落地成本 | 建议 |
|---|---|---|---|
| **npm/pnpm Actions Cache** | 站点构建每次 `npm ci`/`pnpm install` 下载依赖，耗时且消耗 runner 资源 | 低 | 给 `deploy-site-v2.yml`、`deploy-docs-site.yml` 加 `cache: npm` / `cache: pnpm` |
| **Dependabot npm/pnpm** | 自动更新 Next.js/VitePress 依赖 | 低 | 在 `.github/dependabot.yml` 增加 `package-ecosystem: npm` 针对 `donglicao-site-v2/`、`docs-site/`、`chat-web/` |
| **Dependabot alerts** | 主动发现高风险漏洞 | 低 | 在仓库 Settings → Security → Dependabot alerts 启用 |
| **Actions Artifacts 保留策略** | 避免长期 Artifact 占用存储 | 低 | 若产生 Artifact，设置 `retention-days: 7` |
| ** reusable workflow for Pages deploy** | 三个 Pages 工作流内容重复 | 中 | 提取 `deploy-cloudflare-pages.yml` reusable workflow，减少重复 |

---

## 4. Google

### 4.1 已使用

| 功能 | 用途 | 状态 |
|---|---|---|
| **Gemini/Gemma API** | `google_flash_lite`、`google_flash`、`google_pro`、`google_gemma4` 等后端 | ✅ 在路由池，有 budget |
| **Google AI model discovery** | 计划中的 `scripts/inventory_google_models.py`（参考 `docs/archive/.../2026-05-26-cloudflare-google-maximization.md`） | ❌ 未实现 |

### 4.2 未使用 / 可优化

| 功能 | 价值 | 落地成本 | 建议 |
|---|---|---|---|
| **Google Search Console + sitemap** | 让 `www.donglicao.com`、`docs.donglicao.com`、`app.donglicao.com` 被索引 | 低 | 生成 `sitemap.xml`/`robots.txt`，Next.js 可用 `next-sitemap`；验证域名所有权 |
| **Google Analytics 4 / Google Tag** | 追踪官网访问、转化 | 低 | 在 `donglicao-site-v2` 加 GA4/GTM snippet（注意 CSP） |
| **Sign in with Google** | 降低控制台注册门槛 | 中 | 在 `chat-web` 登录/注册加 Google OAuth，服务端用 `routes/oauth_google.py` 验证 JWT |
| **Google AI 模型自动发现** | 每季度/月自动列出可用 Gemini 模型并 diff | 低 | 实现 `scripts/inventory_google_models.py`，可集成到 GitHub Actions 定时任务 |

---

## 5. Telegram（已退役）

根据 `AGENTS.md` 硬规则：

> **禁止**重新注册 `/telegram` 路由、webhook 或出站通知。

因此本次审计**不推荐**任何 Telegram 相关优化。若需要消息/告警通道，建议使用：
- 飞书 Lark（已有 `lark-*` skill 集）
- 企业微信
- 邮件 / SMS

---

## 6. 推荐落地顺序

### P0（本周内）

1. **修复 GitHub Deploy 失败根因** — 已完成：JDCloud 设备存储切 Redis，`/device/v1/health` 已恢复。
2. **给站点部署工作流加依赖缓存**
   - `deploy-site-v2.yml`：`actions/setup-node@v4` 加 `cache: npm`
   - `deploy-docs-site.yml`：`actions/setup-node@v4` 加 `cache: pnpm`
3. **开启 Dependabot alerts** 和 **Dependabot npm 覆盖**。

### P1（本月内）

4. **Cloudflare Turnstile** 接入注册/登录页。
5. **Google Search Console + sitemap** 上线。
6. **提取 Pages 部署 reusable workflow**，减少三份工作流重复。
7. **实现 `scripts/inventory_google_models.py`** 与 nightly GitHub Actions，自动追踪 Google 模型变化。

### P2（后续）

8. **Cloudflare Workers** 做 chat-web 配置下发或 API 边缘 fallback。
9. **Cloudflare AI Gateway** 统一 CF/Google 模型流量。
10. **Google Analytics 4 / Sign in with Google**。

---

## 7. 验证清单

- [ ] `deploy-site-v2.yml` 构建时间缩短（加 npm cache 前后对比）
- [ ] `deploy-docs-site.yml` 构建时间缩短（加 pnpm cache 前后对比）
- [ ] Dependabot alerts 页面可访问
- [ ] `https://chat.donglicao.com/device/v1/health` 持续 200 + `production_ready=true`
- [ ] `https://www.donglicao.com/sitemap.xml` 可被访问
