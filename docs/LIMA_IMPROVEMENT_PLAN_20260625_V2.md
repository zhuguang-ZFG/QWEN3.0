# LiMa 改进计划（基于 GitHub 全链路参考）— 详细版 v2

> 依据：`C:\Users\zhugu\.qclaw\workspace\lima-github-references_20260625.md`
> 制定时间：2026-06-25
> 版本：v2（细化到文件级、页面级、API 级、工时粒度）

---

## 一、背景与现状

### 1.1 已具备的优势

| 层级 | 现有能力 |
|------|---------|
| 服务器端 | 170+ AI 后端、五层量子路由、设备网关、远程 OTA、固件远程证明、会话记忆、上下文流水线、多模态生成 |
| 硬件端 | u1-grbl 绘图/写字机、u8-xiaozhi 语音助手、2D 数字人、OTA 灰度/回滚/签名、ESP32 多板适配 |
| 小程序端 | uni-app Vue 3 + TS + wot-design-uni，20+ 页面：设备列表/绑定/AI 对话/创作/智能体/声纹/配网/隐私 |
| 官网 | 暗色量子星云主题、Canvas 星云/轨道动画、Hero 视频、Ken Burns 动效、SEO meta + Schema.org |
| 控制台 | 原生 HTML/CSS/JS、太阳系 Canvas 背景、SSE 流式聊天、语音通话页、CSP 安全策略 |

### 1.2 现有差距详细清单

| # | 领域 | 缺口 | 严重度 | 参考项目 | 影响 |
|---|------|------|--------|---------|------|
| G1 | 开发者接入 | 无独立文档站 | 🔴 | VitePress / Docusaurus | 开发者无法自主接入 |
| G2 | 开发者接入 | 无 OpenAPI 规范 | 🔴 | Redoc | API 不可机器消费 |
| G3 | 开发者接入 | 无 API Playground | 🔴 | Open WebUI / Monaco | 无法在线试用 |
| G4 | 商业化 | 无定价页 | 🔴 | shadcn-landing-page | 无法转化 |
| G5 | 商业化 | 无 API Key 自助管理 | 🟡 | One API | 人工分配 |
| G6 | 商业化 | 无用量计费体系 | 🟡 | One API | 无透明消费 |
| G7 | 控制台 | 无登录/注册 | 🟡 | Auth.js | 无用户体系 |
| G8 | 控制台 | 无设备详情/管理 | 🟡 | shadcn-dashboard | 体验停留在 Demo |
| G9 | 控制台 | 无多模型切换 | 🟡 | Open WebUI / Lobe Chat | 单模型 |
| G10 | 控制台 | 无会话列表/管理 | 🟡 | Open WebUI | 无历史 |
| G11 | 控制台 | 无文件上传 | 🟢 | Lobe Chat | 无素材导入 |
| G12 | 官网 | 无产品独立详情页 | 🟡 | shadcn-landing-page | 信息不够深 |
| G13 | 官网 | 无集成生态展示 | 🟢 | LiteLLM logo wall | 背后实力未展示 |
| G14 | 官网 | FAQ 仅 4 条 | 🟢 | — | 常见问题覆盖不全 |
| G15 | 官网 | 无社媒/备案 | 🟢 | — | 品牌可信度 |
| G16 | 官网 | 无博客/更新日志 | 🟢 | VitePress blog | 无内容运营阵地 |
| G17 | 官网 | 无 i18n 英文版 | 🟢 | next-i18n | 国际曝光受限 |
| G18 | 官网 | 原生 HTML 难扩展 | 🟡 | Next.js + shadcn/ui | 长期维护成本 |
| G19 | 小程序 | 缺 OTA 升级页 | 🟡 | esp-iot-solution | 有 API 无页面 |
| G20 | 小程序 | 缺用量统计页 | 🟡 | one-api | 用户无法看消耗 |
| G21 | 小程序 | 缺通知中心 | 🟡 | — | 有推送 API 无展示 |
| G22 | 小程序 | 创作结果无预览/分享 | 🟢 | — | 结果仅设备端可见 |
| G23 | 管理面板 | 无独立管理面板 | 🟡 | xiaozhi manager-web | 运维不直观 |
| G24 | 平台化 | 无 RAG 知识库 | 🟢 | Dify | 语音助手知识有限 |
| G25 | 平台化 | 无 Agent 工作流 | 🟢 | Dify | 创作流程不可编排 |
| G26 | 平台化 | 无多租户 | 🟢 | One API / ThingsBoard | 企业级受限 |
| G27 | 平台化 | 无 SDK | 🟢 | LiteLLM SDK | 接入门槛高 |

---

## 二、总体策略

```
Phase A (P0, 1 周)  —— 打通"看到 → 试用 → 付费"转化漏斗
Phase B (P1, 2 周)  —— 控制台用户体系 + 商业化闭环 + 官网内容扩展
Phase C (P2, 3-4 周) —— 技术栈升级 + 小程序页面补齐 + API Playground
Phase D (P3, 按需)   —— SDK、规则引擎、RAG、Agent、多租户
```

核心原则：
1. 不改服务器端核心路由/网关代码，仅做前端 + 文档 + 新增页面。
2. 复用已有后端 API（`/device/v1/app/*`、`/v1/chat/completions`、`/v1/images/generations`），避免新后端开发。
3. 优先用 VitePress / 原生 HTML / 轻量方案，Next.js 迁移推迟到 Phase C。
4. 每个交付物有明确的文件路径、验收标准、工时估算。

---

## 三、Phase A：P0 立即执行（预计 5-7 天）

### A-1 搭建 VitePress 开发者文档站

**目标**：开发者可自助阅读 API 文档并完成首次请求。

**文件结构**：
```
docs-site/
├── package.json
├── .vitepress/
│   ├── config.ts          # VitePress 配置（标题、导航、搜索）
│   └── theme/
│       └── index.ts       # 自定义主题（量子星云暗色风格）
├── index.md               # 首页（项目介绍 + 快速导航）
├── guide/
│   ├── getting-started.md # 5 分钟接入
│   ├── api-key.md         # 获取 API Key
│   └── first-request.md   # 第一个请求
├── api/
│   ├── authentication.md # 认证方式（Bearer Token）
│   ├── chat-completions.md # Chat Completions（OpenAI 兼容）
│   ├── image-generations.md # 图像生成
│   ├── device-control.md  # 设备控制 API
│   ├── voice.md           # 语音交互 API
│   └── errors.md          # 错误码表
├── device/
│   ├── firmware-build.md  # ESP32 固件编译
│   ├── grbl-config.md     # Grbl 配置
│   ├── ota.md             # OTA 升级
│   └── hardware.md        # 硬件参考
└── changelog/
    └── index.md           # 更新日志
```

**详细步骤**：
1. `pnpm create vitepress docs-site` 初始化。
2. 配置 `config.ts`：站点标题 `LiMa 文档`、中文导航、本地搜索。
3. 编写 `guide/getting-started.md`：安装 SDK → 获取 API Key → 发送第一个请求 → 接收响应。
4. 编写 `api/chat-completions.md`：端点 URL、请求体、响应体、流式参数、示例（cURL + Python）。
5. 编写 `api/device-control.md`：设备绑定、任务下发、状态查询、OTA。
6. 编写 `api/errors.md`：从服务器错误码枚举整理（`device_logic/http.py` 的 `err()` 定义）。
7. 部署到 VPS nginx 子域 `docs.donglicao.com`，或 Vercel 静态托管。

**验收标准**：
- [ ] `pnpm dev` 本地可访问。
- [ ] 至少 10 个文档页面。
- [ ] 每个公开 API 端点有请求/响应示例。
- [ ] 暗色主题与官网风格一致（`#07070f` 背景、青色 `#06b6d4` 强调）。
- [ ] `docs.donglicao.com` 可公网访问。

**工时**：3-4 天
**参考**：`vuejs/vitepress`（⭐15k+）

---

### A-2 生成 OpenAPI 3.0 规范

**目标**：机器可读的 API 规范，为 Redoc 文档和 SDK 自动生成打基础。

**详细步骤**：
1. 本地启动 `python -m uvicorn server:app`，导出 `http://localhost:8080/openapi.json`。
2. 人工裁剪：仅保留 `/v1/chat/completions`、`/v1/images/generations`、`/device/v1/app/*` 公开端点，移除 `/internal/*`、`/admin/*`、`/fleet/*` 等内部端点。
3. 补充每个端点的 `summary`、`description`、`example`。
4. 保存为 `docs/openapi.yaml`（YAML 格式，便于人工维护）。
5. 在 VitePress 中嵌入 Redoc 渲染（`api/reference.md` 引用 Redoc CDN）。

**验收标准**：
- [ ] `docs/openapi.yaml` 存在且通过 `redocly lint` 校验。
- [ ] 覆盖所有公开端点，不含任何内部/管理端点。
- [ ] 每个端点至少 1 个 request example + 1 个 response example。
- [ ] VitePress 中可渲染为可读的 API 参考页。

**工时**：1-2 天
**参考**：FastAPI `app.openapi()`、`Redocly/redoc`（⭐23k+）

---

### A-3 新增定价页

**目标**：用户可了解各档位配额与价格。

**文件**：`donglicao-site/pricing.html`

**页面结构**：
```html
<!-- 复用 styles.css 变量，暗色主题 -->
<section class="pricing-hero">
  <h1>选择适合你的创作方案</h1>
  <p>从免费开始，随时升级</p>
</section>

<section class="pricing-grid">
  <!-- 4 列卡片 -->
  <div class="pricing-card plan-free">
    <h2>免费版</h2>
    <div class="price">¥0<span>/月</span></div>
    <ul>
      <li>每日 50 次 AI 对话</li>
      <li>基础模型（GPT-3.5 级别）</li>
      <li>1 台设备接入</li>
      <li>社区支持</li>
    </ul>
    <a href="chat.donglicao.com/register" class="btn">免费开始</a>
  </div>
  <!-- 创作者版 ¥49/月、团队版 ¥199/月、企业版 联系销售 -->
</section>

<section class="pricing-faq">
  <!-- 定价相关 FAQ 5 条 -->
</section>
```

**定价策略建议**：
| 档位 | 月费 | AI 对话 | 设备数 | SVG 生成 | API Key | 支持 |
|------|------|---------|--------|---------|---------|------|
| 免费版 | ¥0 | 50/天 | 1 台 | ❌ | ❌ | 社区 |
| 创作者版 | ¥49 | 500/天 | 3 台 | ✅ | 1 个 | 邮件 |
| 团队版 | ¥199 | 无限 | 10 台 | ✅ | 5 个 | 专属客服 |
| 企业版 | 联系销售 | 不限 | 不限 | ✅ | 不限 | SLA + 定制 |

**验收标准**：
- [ ] `donglicao-site/pricing.html` 完成，4 档卡片响应式布局。
- [ ] 移动端 375px 可阅读。
- [ ] CTA 链接到 `chat.donglicao.com/register`（暂可 404）。
- [ ] Lighthouse Accessibility ≥ 95。

**工时**：1 天
**参考**：`nobruf/shadcn-landing-page` Pricing 区块

---

### A-4 首页代码示例多语言 Tab

**目标**：覆盖 Python / cURL / JavaScript / Go 四种语言的接入示例。

**文件**：修改 `donglicao-site/index.html` 开发者区 + 新增 `donglicao-site/js/code-tabs.js`。

**实现**：
```html
<div class="code-tabs" role="tablist">
  <button class="tab active" data-lang="python" role="tab">Python</button>
  <button class="tab" data-lang="curl" role="tab">cURL</button>
  <button class="tab" data-lang="javascript" role="tab">JavaScript</button>
  <button class="tab" data-lang="go" role="tab">Go</button>
</div>
<pre class="code-panel" data-lang="python"><code>...</code></pre>
<pre class="code-panel" data-lang="curl" hidden><code>...</code></pre>
<!-- ... -->
```

```js
// code-tabs.js
document.querySelectorAll('.code-tabs .tab').forEach(tab => {
  tab.addEventListener('click', () => {
    const lang = tab.dataset.lang;
    tab.parentElement.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    tab.closest('section').querySelectorAll('.code-panel').forEach(p => {
      p.hidden = p.dataset.lang !== lang;
    });
  });
});
```

**验收标准**：
- [ ] 4 个语言 Tab 可切换，默认 Python。
- [ ] 每个代码块语法正确（可直接复制执行）。
- [ ] 响应式：移动端 Tab 变为下拉。

**工时**：0.5 天

---

### A-5 扩充 FAQ 至 12 条

**文件**：修改 `donglicao-site/index.html` FAQ 区块。

**新增 FAQ 条目**：
1. LiMa 支持哪些 AI 模型？（170+ 后端、30+ 供应商、GPT/Claude/DeepSeek/Groq 等）
2. 设备兼容哪些开发板？（ESP32-S3、ESP32-C3 等，参见硬件参考）
3. 数据是否安全？（远程证明、A/B 分区、签名验证、TLS 传输）
4. 如何部署？（Docker 一键部署 / VPS / 本地开发）
5. 支持私有化部署吗？（企业版支持，联系销售）
6. 如何计费？（Token 计费，详见定价页）
7. 可以退款吗？（7 天无理由退款，联系客服）
8. 支持多种设备协同吗？（多设备协同、事件溯源已支持）
9. API 有速率限制吗？（按档位限制，团队版 60 RPM）
10. 固件如何升级？（OTA 远程升级，支持灰度/回滚）
11. 小程序支持哪些语言？（中简/繁、英语、德语、葡萄牙语、越南语）
12. 如何获取技术支持？（社区 → 邮件 → 专属客服，按档位）

**验收标准**：
- [ ] FAQ 区块从 4 条扩展到 12 条。
- [ ] 支持展开/折叠（`<details>` 原生标签或 JS accordion）。
- [ ] 增加结构化数据 `FAQPage` Schema.org JSON-LD。

**工时**：0.5 天

---

### A-6官网 Footer 补完

**文件**：修改 `donglicao-site/index.html` Footer 区块。

**新增内容**：
- 微信公众号二维码图片（`assets/wechat-qr.png`）
- 微博/B站/抖音图标链接（SVG inline）
- ICP 备案号文本
- 产品链接：首页 / 定价 / 文档 / 控制台
- 法律链接：隐私政策 / 用户协议

**验收标准**：
- [ ] Footer 含 5 个社媒入口。
- [ ] ICP 备案号可见。
- [ ] 产品/法律链接可跳转。

**工时**：0.5 天

---

## 四、Phase B：P1 近期执行（预计 10-14 天）

### B-1 控制台登录/注册页

**目标**：用户可通过邮箱密码或微信扫码登录控制台。

**文件**：
- `chat-web/login.html` — 登录页
- `chat-web/register.html` — 注册页
- `chat-web/js/auth.js` — 认证逻辑
- `chat-web/js/api.js` — API 封装

**后端适配**：
- `device_logic/db.py`：`v2_account` 表新增 `email TEXT DEFAULT ''`、`password_hash TEXT DEFAULT ''` 字段。
- `routes/device_app_auth.py`：新增 `POST /device/v1/app/auth/register`（邮箱+密码注册）和 `POST /device/v1/app/auth/login`（邮箱+密码登录）端点，复用现有 JWT 签发逻辑。
- 微信扫码登录：生成扫码 URL → 回调写入 JWT → 前端轮询 `/auth/wechat/status`。

**登录页结构**：
```
┌─────────────────────────────────┐
│  LiMa 控制台                      │
│                                 │
│  [邮箱] [密码]                    │
│  [登录]  [微信扫码登录]            │
│                                 │
│  没有账号？ [去注册]               │
│  忘记密码？                       │
└─────────────────────────────────┘
```

**验收标准**：
- [ ] 邮箱+密码可注册/登录。
- [ ] 微信扫码登录入口可见（可暂为占位 URL）。
- [ ] JWT 存储在 `localStorage`，自动附加到后续请求 Header。
- [ ] 未登录访问控制台时自动跳转 `/login.html`。

**工时**：2-3 天
**参考**：`next-shadcn-dashboard-starter` Auth.js

---

### B-2 API Key 管理页

**目标**：用户可自助创建/删除/查看 API Key。

**文件**：
- `chat-web/keys.html` — Key 管理页
- `chat-web/js/keys.js` — 前端逻辑

**后端适配**：
- `device_logic/db.py`：新增 `v2_api_key` 表 `(id, account_id, key_prefix, key_hash, name, status, created_at, expires_at, daily_limit)`。
- `routes/device_app_auth.py`：新增 `POST /device/v1/app/keys`（创建 Key）、`GET /device/v1/app/keys`（列出 Key）、`DELETE /device/v1/app/keys/{id}`（删除 Key）。

**页面结构**：
```
┌──────────────────────────────────────┐
│  API Key 管理                           │
│                                      │
│  [+ 创建新 Key]                        │
│                                      │
│  ┌────────┬──────┬──────┬──────┐    │
│  │ 名称     │ 前缀  │ 状态   │ 操作  │    │
│  │ my-app  │ sk-···│ active │ 删除  │    │
│  │ test    │ sk-···│ active │ 删除  │    │
│  └────────┴──────┴──────┴──────┘    │
│                                      │
│  新建时仅显示一次完整 Key，之后仅前缀    │
└──────────────────────────────────────┘
```

**验收标准**：
- [ ] 可创建 Key，创建时仅显示一次完整值 + 复制按钮。
- [ ] 列表仅显示前缀（`sk-xxx...` 后 4 位）。
- [ ] 可删除 Key（确认弹窗）。
- [ ] 未登录跳转登录页。

**工时**：1-2 天
**参考**：`songquanpeng/one-api` Key 管理

---

### B-3 用量统计页

**目标**：用户可查看 Token 消耗、请求次数、费用明细。

**文件**：
- `chat-web/usage.html` — 用量统计页
- `chat-web/js/usage.js` — 图表逻辑
- 引入 ECharts CDN（`https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js`）

**后端适配**：
- `routes/device_app_stats.py`：新增 `GET /device/v1/app/stats/usage?days=30` — 返回每日 Token 消耗、请求次数、费用估算。
- 数据源：`v2_task` 表（任务记录）+ `observability/` 指标。

**页面结构**：
```
┌─────────────────────────────────────┐
│  用量统计                               │
│                                     │
│  [本月概览]                            │
│  Token 总消耗: 1.2M   请求: 3,200      │
│  预估费用: ¥45.6                       │
│                                     │
│  [每日 Token 消耗 - 折线图]              │
│  [请求次数分布 - 柱状图]                 │
│  [按能力分布 - 饼图: 写字/绘图/对话]      │
│                                     │
│  [明细表格: 日期/类型/Token/费用]        │
└─────────────────────────────────────┘
```

**验收标准**：
- [ ] 折线图展示近 30 天每日 Token 消耗。
- [ ] 饼图展示能力分布（write_text / draw_generated / chat）。
- [ ] 明细表格支持分页。
- [ ] EChart 暗色主题。

**工时**：1-2 天
**参考**：`songquanpeng/one-api` 用量面板、`next-shadcn-dashboard-starter` 图表

---

### B-4 设备管理页

**目标**：控制台可查看和管理已绑定设备。

**文件**：
- `chat-web/devices.html` — 设备管理页
- `chat-web/js/devices.js` — 前端逻辑

**后端**：复用 `GET /device/v1/app/devices`（已有）、`GET /device/v1/app/devices/{id}`（已有）、`GET /device/v1/app/devices/{id}/status`（已有）。

**页面结构**：
```
┌──────────────────────────────────────┐
│  设备管理                               │
│                                      │
│  [+ 添加设备]                          │
│                                      │
│  ┌──────────┬────┬──────┬────┬────┐  │
│  │ 设备名称   │ SN │ 状态   │ 版本 │ 操作│  │
│  │ 绘图机-01  │ ..│ 在线   │ 1.3 │ 详情│  │
│  │ 写字机-02  │ ..│ 离线   │ 1.2 │ 详情│  │
│  └──────────┴────┴──────┴────┴────┘  │
│                                      │
│  [点击详情 → 右侧抽屉展开]               │
│  抽屉: 设备信息 / 固件版本 / 最近任务 /   │
│        在线状态 / 解绑按钮               │
└──────────────────────────────────────┘
```

**验收标准**：
- [ ] 设备列表有在线/离线状态指示。
- [ ] 点击"详情"展开抽屉，显示设备信息 + 最近 5 条任务。
- [ ] 支持解绑（确认弹窗）。
- [ ] 实时状态通过 WebSocket `/device/v1/app/devices/{id}/status/ws` 更新。

**工时**：2-3 天
**参考**：`next-shadcn-dashboard-starter`、`thingsboard/thingsboard` 设备列表

---

### B-5 官网集成生态 logo 墙

**文件**：修改 `donglicao-site/index.html` 产品区后新增区块。

**展示内容**：
- 20+ 代表性 AI 模型/供应商 logo（GPT-4o、Claude、DeepSeek、Groq、NVIDIA、OpenRouter、Cloudflare、Google AI、Mistral、SiliconFlow、Zhipu、Baidu、Tencent、Volcengine、Aliyun、LongCat、Llama、Gemini 等）
- 懒加载（`loading="lazy"`）
- 灰度 → 彩色 hover 效果

**验收标准**：
- [ ] 至少 20 个 logo 展示。
- [ ] 移动端 2 列、桌面端 5 列。
- [ ] 首屏外懒加载。

**工时**：0.5 天

---

### B-6 星云路由节点悬停交互

**文件**：修改 `donglicao-site/js/galaxy.js`。

**实现**：
- 鼠标悬停节点时显示 `tooltip`：模型名称、平均延迟、价格级别（免费/低/中/高）。
- 节点数据从静态 JSON 或内联对象读取。
- `tooltip` 使用 CSS `position: absolute` + JS 坐标计算。

**节点数据示例**：
```js
const NODE_INFO = {
  gpt4o:    { name: 'GPT-4o',     latency: '300-800ms', price: '中' },
  claude:   { name: 'Claude 3.5', latency: '200-500ms', price: '中' },
  deepseek: { name: 'DeepSeek',   latency: '100-300ms', price: '低' },
  groq:     { name: 'Groq',       latency: '50-150ms',  price: '免费' },
  // ...
};
```

**验收标准**：
- [ ] 悬停至少 10 个节点可显示 tooltip。
- [ ] tooltip 含模型名/延迟/价格。
- [ ] 移动设备触摸也可触发（`touchstart`）。

**工时**：1 天

---

### B-7 产品独立详情页

**文件**：
- `donglicao-site/product-draw.html` — AI 绘图机
- `donglicao-site/product-write.html` — AI 写字机
- `donglicao-site/product-human.html` — 2D 数字人

**每页结构**：
```
1. Hero 区 — 产品名 + 标语 + 演示视频/图片
2. 功能特性 — 4 个图标卡片
3. 技术规格 — 表格
4. 使用场景 — 3 张轮播卡片
5. 常见问题 — 4 条
6. CTA — "立即购买" / "查看定价" / "技术文档"
```

**验收标准**：
- [ ] 3 个产品页均完成。
- [ ] 每页含 `og:image` + `canonical` SEO 标签。
- [ ] 移动端响应式。
- [ ] 导航栏含"产品"下拉菜单链接到 3 个页面。

**工时**：2-3 天
**参考**：`nobruf/shadcn-landing-page` Features 区块

---

### B-8 博客/更新日志骨架

**方案**：在 VitePress 文档站中集成博客（`docs-site/changelog/`），不单独部署。

**内容**：
- `changelog/2026-06-25-phase5.md` — Phase 5 小程序增强发布说明（已有的 progress.md 内容精简为用户视角）
- `changelog/2026-06-24-coding-retirement.md` — 编码能力退役说明
- `changelog/index.md` — 时间线汇总页

**验收标准**：
- [ ] VitePress 文档站 `/changelog/` 可访问。
- [ ] 至少 2 篇更新日志。
- [ ] 时间线页面按时间倒序排列。

**工时**：1 天

---

## 五、Phase C：P2 中期执行（预计 3-4 周）

### C-1 官网技术栈迁移到 Next.js

**目标**：将纯 HTML 官网迁移到 Next.js + Tailwind + shadcn/ui，实现组件化、i18n、SSG。

**文件结构**：
```
donglicao-site-v2/
├── package.json
├── next.config.js          # output: 'export' 静态导出
├── tailwind.config.js
├── app/
│   ├── layout.tsx          # 根布局（暗色主题、SEO meta）
│   ├── page.tsx            # 首页（1:1 还原现有 index.html）
│   ├── pricing/page.tsx    # 定价页
│   ├── product-draw/page.tsx
│   ├── product-write/page.tsx
│   ├── product-human/page.tsx
│   └── blog/
│       ├── page.tsx        # 博客列表
│       └── [slug]/page.tsx # 博客详情
├── components/
│   ├── hero.tsx
│   ├── galaxy-canvas.tsx   # 星云 Canvas 动画
│   ├── bento-grid.tsx      # 产品 Bento 布局
│   ├── pricing-cards.tsx
│   ├── faq-accordion.tsx
│   ├── footer.tsx
│   └── code-tabs.tsx
├── messages/
│   ├── zh.json             # 中文文案
│   └── en.json             # 英文文案
└── public/
    └── assets/              # 图片、视频等
```

**迁移策略**：
1. 先用 `next create` 初始化项目，`output: 'export'` 静态导出。
2. 逐页迁移：首页 → 定价 → 产品页 → FAQ → Footer。
3. Canvas 动画用 React ref + `useEffect` 封装。
4. i18n 用 `next-intl`，中文为默认，英文为 `/en` 路径。
5. 部署到 VPS（静态文件）或 Vercel。
6. nginx 按域名切换新旧站。

**验收标准**：
- [ ] `next build && next export` 生成静态 HTML。
- [ ] 首页与旧站 1:1 视觉一致。
- [ ] Lighthouse Performance ≥ 90、Accessibility ≥ 95。
- [ ] `/en` 英文版可访问。
- [ ] 旧站保留为 fallback（nginx 301 到新站）。

**工时**：1-2 周
**参考**：`nobruf/shadcn-landing-page`、`next-intl`

---

### C-2 控制台功能增强

| 子任务 | 文件 | 说明 |
|--------|------|------|
| 多模型切换 | `chat-web/chat-ui.js` | 下拉框选择模型（从 `GET /v1/models` 获取列表） |
| 会话列表 | `chat-web/chat-ui.js` | 侧边栏展示历史会话，可切换/删除 |
| Markdown 增强 | `chat-web/chat-messages.js` | 引入 highlight.js 代码高亮 + KaTeX 公式 |
| 文件上传 | `chat-web/chat-ui.js` | 支持图片/SVG 上传（`POST /device/v1/app/assets`） |
| 语音输入 | `chat-web/chat-ui.js` | Web Speech API 已有，增强为可发送语音消息 |
| 设备状态指示 | `chat-web/index.html` | 侧边栏设备列表增加在线/离线圆点（WebSocket） |
| 任务进度条 | `chat-web/chat-ui.js` | 绘图/写字任务展示进度条（轮询 `GET /tasks/{id}`） |

**验收标准**：
- [ ] 聊天界面可切换 5+ 模型。
- [ ] 会话列表可查看/切换/删除。
- [ ] 代码块有语法高亮。
- [ ] 支持图片/SVG 上传到素材库。
- [ ] 设备在线状态实时更新。

**工时**：1-2 周
**参考**：`open-webui/open-webui`（⭐80k+）、`lobehub/lobe-chat`（⭐50k+）

---

### C-3 API Playground

**目标**：开发者可在线编辑并发送 API 请求，实时查看流式响应。

**文件**：
- `chat-web/playground.html`
- `chat-web/js/playground.js`
- 引入 Monaco Editor CDN
- 引入 ECharts（用于 Token 统计可视化）

**页面结构**：
```
┌──────────────────────────────────────────┐
│ API Playground                             │
│                                           │
│ ┌──── 左栏: 请求编辑 ────┐ ┌─── 右栏: 响应 ──┐ │
│ │ Method: POST           │ │ Status: 200     │ │
│ │ URL: /v1/chat/completions│ │ Time: 1.2s       │ │
│ │ Headers:                │ │ Tokens: 123     │ │
│ │   Authorization: Bearer  │ │                 │ │
│ │ Body (Monaco Editor):   │ │ Response:       │ │
│ │ {                       │ │ {"choices":[...]}│ │
│ │   "model": "lima",      │ │                 │ │
│ │   "messages": [...]      │ │ [流式实时追加]    │ │
│ │ }                       │ │                 │ │
│ │                         │ │                 │ │
│ │ [发送请求]  [复制 cURL]   │ │                 │ │
│ └─────────────────────────┘ └─────────────────┘ │
│                                           │
│ [历史请求列表: 时间/URL/状态/Token]          │
└──────────────────────────────────────────┘
```

**验收标准**：
- [ ] Monaco Editor 可编辑 JSON 请求体。
- [ ] 支持选择模型（下拉框）。
- [ ] 可调节 `temperature`、`max_tokens`、`stream` 参数。
- [ ] 流式响应实时展示。
- [ ] 可生成 cURL 命令并复制。
- [ ] 历史请求存在 `localStorage`。

**工时**：2-3 天
**参考**：Open WebUI Playground、Monaco Editor

---

### C-4 Redoc API 文档

**目标**：从 OpenAPI 规范自动生成交互式 API 参考文档。

**文件**：`docs-site/api/reference.md`

**实现**：
```html
<Redoc spec-url="/openapi.yaml"></Redoc>
<script src="https://cdn.redocly.com/redoc/latest/bundles/redoc.standalone.js"></script>
```

**验收标准**：
- [ ] 三栏布局（导航/文档/示例）。
- [ ] 每个端点可展开请求/响应示例。
- [ ] 支持暗色主题。

**工时**：0.5 天
**参考**：`Redocly/redoc`（⭐23k+）

---

### C-5 小程序端增强

| 子任务 | 页面路径 | 后端 API（已有） | 说明 |
|--------|---------|----------------|------|
| OTA 升级页 | `pages/ota/index` | `GET /device/v1/ota/check`、`POST /device/v1/ota/start` | 展示当前版本、可用固件、升级进度、回滚按钮 |
| 用量统计页 | `pages/usage/index` | `GET /device/v1/app/stats/usage` | ECharts 小程序版，展示 Token/任务/费用 |
| 通知中心 | `pages/notifications/index` | `GET /device/v1/app/notifications/subscriptions` | 订阅管理 + 历史通知列表 |
| 创作结果预览 | `pages/create/result` | `GET /device/v1/app/tasks/{id}` | SVG 渲染 + 保存相册 + 分享好友/朋友圈 |
| 设备分享 | `pages/v2/device-share/index` | `POST /devices/{id}/share`、`POST /shares/{token}/accept` | 分享二维码 + 访客列表 + 权限管理 |

**每个页面的详细需求**：

**OTA 升级页**：
```
┌─────────────────────────────────┐
│  固件升级                          │
│                                 │
│  当前版本: v1.3.0                 │
│  可用版本: v1.4.0 (2026-06-25)    │
│  更新内容: 修复绘图精度、新增...    │
│                                 │
│  [升级到 v1.4.0]                  │
│  [回滚到 v1.2.0]                  │
│                                 │
│  升级进度: ████████░░ 80%         │
│  状态: 正在下载固件...             │
└─────────────────────────────────┘
```

**用量统计页**：
```
┌─────────────────────────────────┐
│  用量统计                          │
│                                 │
│  本月 Token: 1.2M   请求: 3200    │
│  预估费用: ¥45.6                   │
│                                 │
│  [折线图: 近 30 天 Token 趋势]      │
│  [饼图: 写字/绘图/对话 分布]        │
│                                 │
│  [明细列表: 日期/类型/Token/费用]   │
└─────────────────────────────────┘
```

**通知中心**：
```
┌─────────────────────────────────┐
│  通知中心                          │
│                                 │
│  [订阅设置]                        │
│  ☑ 任务完成通知                    │
│  ☑ 设备离线通知                    │
│  ☐ 固件更新通知                    │
│                                 │
│  [历史通知]                        │
│  ✓ 任务"画一个猫"已完成 | 10:30     │
│  ✗ 设备"写字机"已离线  | 09:15     │
└─────────────────────────────────┘
```

**验收标准**：
- [ ] 5 个新页面均可访问。
- [ ] OTA 页展示升级进度。
- [ ] 用量页 ECharts 图表可用。
- [ ] 通知页可管理订阅 + 查看历史。
- [ ] 创作结果页可分享到微信。
- [ ] 分享页可生成二维码。

**工时**：1-2 周

---

## 六、Phase D：P3 长期规划（按需启动）

| 序号 | 任务 | 详细说明 | 参考 | 预估工时 |
|------|------|---------|------|---------|
| D-1 | Python SDK | `lima-sdk-python/`：封装 Chat Completions / 图像生成 / 设备控制 API | LiteLLM SDK | 1 周 |
| D-2 | JavaScript SDK | `lima-sdk-js/`：同上，TypeScript 类型 | OpenAI JS SDK | 1 周 |
| D-3 | Go SDK | `lima-sdk-go/`：同上 | — | 1 周 |
| D-4 | 规则引擎可视化编排 | 在管理面板中提供拖拽式规则引擎，支持设备触发条件 → 执行动作 | ThingsBoard Rule Engine | 4-6 周 |
| D-5 | RAG 知识库 | 集成向量数据库，支持文档上传 → 向量化 → 检索增强生成 | Dify、xiaozhi-server | 2-4 周 |
| D-6 | Agent 工作流 | 可视化编排 Agent 步骤：输入 → 理解 → 规划 → 执行 → 验证 | Dify Workflow | 4-8 周 |
| D-7 | 多租户体系 | 租户隔离、配额管理、资源计费、权限 RBAC | One API、ThingsBoard | 4-6 周 |
| D-8 | 管理面板 | Vue/React 独立管理面板：设备/用户/渠道/日志/审计 | xiaozhi manager-web | 2-3 周 |

---

## 七、完整工时汇总

| Phase | 任务数 | 预估工时 | 并行度 | 日历周 |
|-------|--------|---------|--------|--------|
| A (P0) | 6 项 | 5-7 天 | 1 人串行 | 1 周 |
| B (P1) | 8 项 | 10-14 天 | 1-2 人并行 | 2 周 |
| C (P2) | 5 项 | 15-25 天 | 1-2 人并行 | 3-4 周 |
| D (P3) | 8 项 | 按需 | — | 按需 |
| **合计** | **27 项** | **30-46 天** | | **6-7 周** |

---

## 八、关键技术与参考映射（完整版）

### 8.1 服务器端改进

| LiMa 模块 | 最佳 GitHub 参考 | Star | 借鉴重点 | 优先级 |
|-----------|-----------------|------|---------|--------|
| `routing_engine.py` | `BerriAI/litellm` | 25k+ | Router 类设计、fallback 策略、成本路由、latency-based routing | P2 |
| `routing_selector/` | `BerriAI/litellm` | 25k+ | 后端排序算法、权重/优先级 | P2 |
| `routing_executor*.py` | `iBreaker/llm-gateway` | — | 串/并行执行 + 降级 | P2 |
| `router_v3/` 后端池 | `BerriAI/litellm` | 25k+ | 后端池管理、健康检查 | P2 |
| `backends_registry/` | LiteLLM + One API | 25k+ | 多渠道权重路由 | P2 |
| `key_pool.py` + `budget_*.py` | `songquanpeng/one-api` | 20k+ | 计费体系、额度管理、用户 Token 管理 | P1 |
| `health_*.py` | `iBreaker/llm-gateway` | — | 健康优先路由、自动故障转移 | P2 |
| `device_gateway/` | `xinnan-tech/xiaozhi-esp32-server` | 9.1k+ | WebSocket 管理、双协议、设备注册 | — |
| `fleet/` + `device_ledger/` | `thingsboard/thingsboard` | 18k+ | 规则引擎、多租户、OTA 分发 | P3 |
| `device_voice/` | xiaozhi-server | 9.1k+ | ASR/TTS/LLM 流式管线 | — |
| `streaming.py` | LiteLLM + llm-gateway | — | SSE 流式代理 | — |
| `context_pipeline/` | `langgenius/dify` | 60k+ | 检索与上下文注入（编码模块已退役） | P3 |
| `session_memory/` | Dify | 60k+ | 持久记忆与学习循环 | P3 |
| `skills/` | Dify | 60k+ | 可注入技能 Markdown | P3 |
| `device_ota/` | `espressif/esp-iot-solution` | — | A/B 分区、签名验证、回滚 | P2 |
| `access_guard.py` | One API | 20k+ | 访问控制、用户体系 | P1 |

### 8.2 Web 端改进

| LiMa 模块 | 最佳 GitHub 参考 | Star | 借鉴重点 | 优先级 |
|-----------|-----------------|------|---------|--------|
| `chat-web/` 控制台 | `open-webui/open-webui` | 80k+ | 多模型切换、RAG、用户管理、Markdown 增强 | P2 |
| `chat-web/` 插件 | `lobehub/lobe-chat` | 50k+ | 插件系统、语音、视觉、PWA | P2 |
| `donglicao-site/` 官网 | `nobruf/shadcn-landing-page` | — | Next.js 落地页、Pricing/FAQ 区块 | P2 |
| 管理仪表盘 | `next-shadcn-dashboard-starter` | — | 仪表盘布局、数据表格、图表 | P1 |
| API 文档 | `Redocly/redoc` | 23k+ | OpenAPI 自动生成、三栏布局 | P0 |
| 文档站 | `vuejs/vitepress` | 15k+ | Markdown 驱动、暗色模式、搜索 | P0 |

### 8.3 固件端改进

| LiMa 模块 | 最佳 GitHub 参考 | Star | 借鉴重点 | 优先级 |
|-----------|-----------------|------|---------|--------|
| `u8-xiaozhi/` | `78/xiaozhi-esp32` | 9k+ | VAD 实时打断、声纹识别、知识库 RAG | P2 |
| `u1-grbl/` | `bdring/Grbl_Esp32` | 1.7k+ | 双电机 gantry、G-code 扩展、Web 配置 | P2 |
| `device_ota/` | `espressif/esp-iot-solution` | — | A/B 分区、签名验证、回滚 | P2 |
| 固件 WebSocket | `espressif/esp-protocols` | — | 官方 WebSocket/MQTT 实现 | — |

### 8.4 小程序端改进

| 改进项 | 参考项目 | 优先级 |
|--------|---------|--------|
| OTA 升级页 | `espressif/esp-iot-solution` | P2 |
| 用量统计页 | `songquanpeng/one-api` | P2 |
| 通知中心 | — | P2 |
| 创作结果预览与分享 | — | P2 |
| 设备分享访客模式 | — | P2 |
| 配网流程优化（蓝牙辅助） | — | P3 |
| 设备实时遥测 | ThingsBoard | P3 |
| 设备分组 | — | P3 |
| 深色模式 | — | P3 |

---

## 九、风险与规避

| # | 风险 | 影响 | 概率 | 规避措施 |
|---|------|------|------|----------|
| R1 | 官网 Next.js 迁移工作量被低估 | 延迟 2-4 周 | 中 | 先静态化部署，再逐步组件化；保留旧站 nginx 回滚 |
| R2 | 用户体系与现有 `device_app_auth` 耦合 | 安全/兼容问题 | 中 | 复用 JWT，补充 email/password_hash 字段，旧 phone 登录保持并存 |
| R3 | OpenAPI 暴露内部端点 | 安全漏洞 | 低 | 人工审核 + 仅暴露 `/v1/*` 和 `/device/v1/app/*` 公开端点 |
| R4 | 文档站与主站风格不一致 | 品牌割裂 | 中 | 统一设计 token（色板、字体、圆角），VitePress 自定义主题 |
| R5 | 控制台功能膨胀导致维护困难 | 技术债 | 中 | 按"页面级"独立迭代，每页独立 JS 文件，避免全局耦合 |
| R6 | 小程序 ECharts 包体积过大 | 可用性 | 低 | 使用 `@es renewed/echarts-mini` 或按需引入 |
| R7 | 定价策略与实际成本不匹配 | 收入损失 | 中 | 先调研后端 Token 成本，设定不低于成本 1.5 倍的价格 |
| R8 | API Playground XSS 风险 | 安全 | 低 | Monaco Editor 沙箱化，禁止外部脚本执行 |

---

## 十、下一步行动（建议本周启动）

| 序号 | 行动 | 负责人 | 预期产出 |
|------|------|--------|---------|
| 1 | 确认产品定价策略（四档配额与价格） | 产品 | 定价表定稿 |
| 2 | 从 FastAPI 导出 OpenAPI JSON 并裁剪 | 开发 | `docs/openapi.yaml` 初稿 |
| 3 | 初始化 VitePress 文档站工程 | 开发 | `docs-site/` 可 `pnpm dev` |
| 4 | 在 `donglicao-site/` 新增 `pricing.html` | 开发 | 定价页可访问 |
| 5 | 扩充 FAQ + Footer 社媒 + 代码多语言 Tab | 开发 | 首页更新 |
| 6 | 规划 `v2_account` 表扩展（email/password_hash） | 开发 | migration 脚本 |
| 7 | 设计控制台登录/注册页原型 | 设计 | Figma/HTML mockup |

---

## 十一、验收总标准

### Phase A 验收
- [ ] `docs.donglicao.com` 可访问，含 10+ 文档页面 + API 参考 + 错误码
- [ ] `donglicao.com/pricing` 上线，四档定价清晰
- [ ] 首页 FAQ 扩充到 12 条 + 代码 Tab + Footer 社媒
- [ ] `docs/openapi.yaml` 通过 lint 校验

### Phase B 验收
- [ ] 控制台支持邮箱注册/登录 + JWT
- [ ] API Key 可创建/删除/列表
- [ ] 用量统计页有 ECharts 图表
- [ ] 设备管理页有列表 + 详情抽屉 + 实时状态
- [ ] 官网有 3 个产品页 + logo 墙 + 星云交互

### Phase C 验收
- [ ] Next.js 官网 `next build && next export` 成功
- [ ] 控制台可切换模型 + 会话列表 + Markdown 高亮 + 文件上传
- [ ] API Playground 可发送请求 + 流式响应 + cURL 生成
- [ ] 小程序新增 5 个页面（OTA/用量/通知/预览/分享）
- [ ] Lighthouse Performance ≥ 90、Accessibility ≥ 95
- [ ] 全量 pytest 保持通过（目前 3730 passed / 17 skipped）

### Phase D 验收（按需）
- [ ] Python/JS/Go SDK 发布到对应包管理器
- [ ] 规则引擎可视化编排可用
- [ ] RAG 知识库可上传文档并检索增强
- [ ] 多租户体系可隔离租户数据与配额