# LiMa 改进计划（基于 GitHub 全链路参考）

> 依据：`C:\Users\zhugu\.qclaw\workspace\lima-github-references_20260625.md`
> 制定时间：2026-06-25
> 目标：补齐官网、控制台、小程序在开发者接入、商业化、可维护性上的短板，同时巩固 LiMa 在 170+ 后端路由、SVG 绘图管线、AI 硬件接入上的差异化优势。

---

## 一、背景与现状

### 1.1 已具备的优势
- **服务器端**：170+ AI 后端、五层量子路由、设备网关、远程 OTA、固件远程证明、会话记忆、上下文流水线。
- **硬件端**：u1-grbl 绘图/写字机、u8-xiaozhi 语音助手、2D 数字人、OTA 灰度/回滚/签名。
- **小程序端**：uni-app Vue 3 + TypeScript，已支持设备绑定、AI 对话、创作任务、声纹、分享、通知、统计分析。
- **官网**：暗色量子星云主题、Canvas 动画、SEO 基础、WebP/视频/Meta 标签。

### 1.2 当前主要短板
| 领域 | 关键缺口 | 影响 |
|------|---------|------|
| 开发者接入 | 无独立文档站、无 API Playground、无 OpenAPI 规范 | 开发者无法自助接入 |
| 商业化 | 无定价页、无用量计费、无 API Key 自助管理 | 难以转化付费用户 |
| 控制台 | 无登录/注册、无设备详情、无量统计、无多模型切换 | 用户体验停留在 Demo 级 |
| 官网工程 | 纯原生 HTML/CSS/JS，难扩展；无 i18n | 长期维护成本高 |
| 运营 | 无博客/更新日志、无社交媒体入口、FAQ 太少 | 缺少内容运营阵地 |

---

## 二、总体策略

1. **先补齐 P0 转化路径**：文档站 + 定价页 + API Playground，让潜在用户能看懂、能用、能付钱。
2. **再完善控制台用户体系**：登录/注册 → API Key → 用量统计 → 设备管理，形成闭环。
3. **同步强化小程序前端页面**：把 Phase 5 已完成的服务端能力（OTA、通知、用量统计、分享）在小程序内做成独立页面。
4. **中期做技术栈升级**：官网迁移到 Next.js + Tailwind + shadcn/ui，文档站用 VitePress，API 文档用 Redoc。
5. **长期做平台化**：SDK、规则引擎、RAG、Agent 工作流、多租户。

---

## 三、分阶段计划

### Phase A：P0 立即执行（预计 1 周）

| 序号 | 任务 | 交付物 | 参考/工具 | 验收标准 |
|------|------|--------|----------|----------|
| A-1 | 搭建开发者文档站 | `docs-site/`（VitePress 初始工程） | `vuejs/vitepress` | 本地 `pnpm dev` 可访问，含快速开始、API 认证、Chat Completions、错误码页面 |
| A-2 | 生成 OpenAPI 3.0 规范 | `docs/openapi.yaml` | FastAPI `openapi.json` | 覆盖 `/v1/chat/completions`、`/v1/images/generations`、设备 API 核心端点 |
| A-3 | 新增定价页 | `donglicao-site/pricing.html` | `nobruf/shadcn-landing-page` Pricing 区块 | 含免费/创作者/团队/企业四档，响应式，链接到控制台注册 |
| A-4 | 首页代码示例多语言 Tab | `donglicao-site/index.html` 开发者区改造 | 原生 JS Tab | 支持 Python / cURL / JavaScript / Go 切换 |
| A-5 | 扩充 FAQ 至 10+ 条 | `donglicao-site/index.html` FAQ 区块 | — | 覆盖设备兼容性、数据安全、部署方式、计费、退款 |
| A-6 | 官网 Footer 增加社媒与备案 | `donglicao-site/index.html` Footer | — | 含微信/微博/B站/抖音图标、ICP 备案号 |

**关键决策**：
- 文档站先以 VitePress 静态站点形式放在 `docs-site/`，部署到 `docs.donglicao.com`（初期可用 VPS nginx 子目录或 Vercel）。
- OpenAPI 规范先从 FastAPI 导出再人工精简，避免一次性暴露内部/实验端点。

---

### Phase B：P1 近期执行（预计 2 周）

| 序号 | 任务 | 交付物 | 参考/工具 | 验收标准 |
|------|------|--------|----------|----------|
| B-1 | 控制台登录/注册 | `chat-web/login.html`、`chat-web/register.html` | Auth.js / 微信扫码 URL | 支持邮箱+密码登录、微信扫码登录入口、JWT 存储 |
| B-2 | API Key 管理页 | `chat-web/keys.html` | `next-shadcn-dashboard-starter` 表格 | 可创建/删除 Key、显示前缀、设置额度 |
| B-3 | 用量统计页 | `chat-web/usage.html` | Chart.js / ECharts | 展示 Token 消耗、请求次数、费用明细、按天图表 |
| B-4 | 设备管理页 | `chat-web/devices.html` | `next-shadcn-dashboard-starter` | 设备列表、在线状态、固件版本、最近任务、详情抽屉 |
| B-5 | 官网集成生态 logo 墙 | `donglicao-site/index.html` 新增区块 | — | 静态展示 20+ 代表性模型/供应商 logo，懒加载 |
| B-6 | 星云路由节点悬停交互 | `donglicao-site/js/galaxy.js` | — | 鼠标悬停节点显示模型名称、延迟区间、价格级别 |
| B-7 | 产品独立详情页 | `donglicao-site/product-draw.html`、`product-write.html`、`product-human.html` | `nobruf/shadcn-landing-page` Features | 每页含功能、规格、场景、演示视频、CTA |
| B-8 | 博客/更新日志骨架 | `donglicao-site/blog/` 或独立 `blog.donglicao.com` | VitePress 博客插件 | 发布第一篇版本更新文章 |

**关键决策**：
- 控制台用户体系复用现有 `device_app_auth` 的 JWT 能力，避免重复造轮子；如需要邮箱密码，则扩展 `v2_account` 表。
- 用量统计先复用 `ops_metrics` 与 `v2_task` 数据，后端提供聚合 API（`GET /device/v1/app/stats/usage` 已具备雏形）。

---

### Phase C：P2 中期执行（预计 3-4 周）

| 序号 | 任务 | 交付物 | 参考/工具 | 验收标准 |
|------|------|--------|----------|----------|
| C-1 | 官网技术栈迁移到 Next.js | `donglicao-site-v2/`（Next.js + Tailwind + shadcn/ui） | `nobruf/shadcn-landing-page` | 首页 1:1 还原，构建输出静态 HTML，Lighthouse 性能 ≥ 90 |
| C-2 | 控制台功能增强 | `chat-web/` 引入模型选择、会话列表、文件上传 | `open-webui/open-webui`、`lobehub/lobe-chat` | 聊天界面可切换模型、展示历史会话、支持图片/SVG 上传 |
| C-3 | API Playground | `chat-web/playground.html` 或 `docs.donglicao.com/playground` | Monaco Editor + SSE | 在线编辑请求、选择模型、调节参数、实时展示流式响应 |
| C-4 | Redoc API 文档 | `docs-site/api.html` | `Redocly/redoc` | 从 `openapi.yaml` 自动生成三栏文档 |
| C-5 | 官网 i18n 英文版 | `donglicao-site/en/` 或 Next.js i18n | next-i18n | 首页、定价、FAQ 英文版可切换 |
| C-6 | 小程序端 OTA 页 | `esp32S_XYZ/server/xiaozhi-esp32-server/main/manager-mobile/pages/ota/` | — | 展示当前版本、可用固件、升级进度、回滚按钮 |
| C-7 | 小程序创作结果预览与分享 | 小程序新增创作结果页 | — | SVG/图片预览、保存相册、分享到微信好友/朋友圈 |
| C-8 | 小程序用量统计页 | 小程序新增 `pages/usage/` | ECharts 小程序版 | Token 消耗、任务数、按天图表 |

**关键决策**：
- 官网迁移采用“并行重构、灰度切换”：新站点构建后与旧站点并存，通过 nginx 按路径或域名切换。
- 控制台增强尽量保持原生 HTML/CSS/JS，避免引入重型框架导致维护负担；必要时用 lit/preact 做局部组件化。

---

### Phase D：P3 长期规划（按需启动）

| 序号 | 任务 | 价值 | 参考 |
|------|------|------|------|
| D-1 | Python / JS / Go SDK | 降低接入门槛 | 参考 LiteLLM SDK |
| D-2 | 规则引擎可视化编排 | 设备自动化 | ThingsBoard |
| D-3 | RAG 知识库集成 | 数字人/语音助手知识增强 | Dify、xiaozhi-server |
| D-4 | Agent 工作流 | 复杂创作流程编排 | Dify |
| D-5 | 多租户体系 | 企业级 SaaS | One API、ThingsBoard |

---

## 四、关键技术与参考映射

| LiMa 模块 | 最佳参考 | 借鉴重点 |
|-----------|---------|---------|
| 文档站 | `vuejs/vitepress` | Markdown 驱动、暗色模式、搜索 |
| API 文档 | `Redocly/redoc` | OpenAPI 自动生成、三栏布局 |
| 官网落地页 | `nobruf/shadcn-landing-page` | Next.js + shadcn/ui + Pricing/FAQ 区块 |
| 控制台 | `open-webui/open-webui`、`lobehub/lobe-chat` | 多模型切换、会话管理、Markdown 渲染 |
| 管理仪表盘 | `next-shadcn-dashboard-starter` | 设备/Key/用量表格与图表 |
| 路由引擎 | `BerriAI/litellm` | Router、fallback、成本路由 |
| 计费/Key 池 | `songquanpeng/one-api` | 多 Key 轮转、额度管理 |
| 设备管理 | `thingsboard/thingsboard` | 规则引擎、可视化仪表盘 |
| 固件 OTA | `espressif/esp-iot-solution` | A/B 分区、签名验证 |

---

## 五、风险与规避

| 风险 | 影响 | 规避措施 |
|------|------|----------|
| 官网 Next.js 迁移工作量被低估 | 延迟 | 先静态化部署，再逐步组件化；保留旧站回滚 |
| 用户体系与现有 `device_app_auth` 耦合 | 安全/兼容 | 复用 JWT，补充邮箱密码字段，迁移旧账号 |
| OpenAPI 暴露内部端点 | 安全 | 人工审核 + 仅暴露 `/v1/*` 公开端点 |
| 文档站与主站风格不一致 | 品牌 | 统一设计 token（色板、字体、按钮） |
| 控制台功能膨胀导致维护困难 | 长期 | 按“页面级”独立迭代，每页独立测试 |

---

## 六、下一步行动（建议本周启动）

1. **确认产品定价策略**（免费/创作者/团队/企业四档的具体配额与价格）。
2. **输出 OpenAPI 3.0 初稿**（从 FastAPI `app.openapi()` 导出并裁剪）。
3. **初始化 VitePress 文档站**（`docs-site/`，部署到 VPS `/var/www/docs` 或 Vercel）。
4. **在 `donglicao-site/` 新增 `pricing.html`**（可先静态，复用现有 CSS 变量）。
5. **规划控制台用户表扩展**（`v2_account` 增加 email/password_hash，与现有 phone 登录并存）。

---

## 七、验收总标准

- [ ] `docs.donglicao.com` 可访问，含快速开始、API 参考、错误码。
- [ ] `donglicao.com/pricing` 上线，四档定价清晰。
- [ ] 控制台支持登录/注册、API Key 管理、用量统计、设备管理。
- [ ] 全量 pytest 保持通过（当前 3730 passed / 17 skipped）。
- [ ] 新页面通过 Lighthouse 性能审计（Performance ≥ 90，Accessibility ≥ 95）。
