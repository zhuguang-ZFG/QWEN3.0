# 更新日志

> 按时间倒序排列。每条记录可点击标题查看详情。

---

## 2026-06-25 Phase C P2：设备任务进度条

- `chat-web/js/devices.js`：设备详情抽屉对活跃任务展示进度条，每 2 秒轮询 `/device/v1/app/tasks/{task_id}` 更新进度。
- `chat-web/devices.html` 新增进度条样式。

## 2026-06-25 Phase C P2：控制台素材上传

- `chat-web/js/asset-upload.js`：输入区新增上传按钮，支持 SVG/图片上传到 `/device/v1/app/assets`。
- `chat-web/index.html` 引入脚本并新增上传按钮。

## 2026-06-25 Phase C P2：控制台历史会话管理

- `chat-web/chat-messages.js` 新增会话管理：会话数据持久化到 `localStorage`，支持保存、切换、删除。
- `chat-web/chat-ui.js` 的「新对话」自动保存当前会话。
- `chat-web/chat-api.js` 在聊天与图片生成完成后保存会话。

## 2026-06-25 Phase C P2：控制台多模型切换

- `chat-web/js/model-selector.js`：顶部工具栏模型选择器，从 `/v1/models` 拉取模型列表，无 Key 时回退 `lima`，选择结果存入 `localStorage`。
- `chat-web/chat-api.js`：`/v1/chat/completions` 使用选中的模型。

## 2026-06-25 Phase C P2：控制台 Markdown 增强

- `chat-web/index.html` 引入 highlight.js 与 KaTeX CDN，更新 CSP。
- `chat-web/chat-messages.js` 支持 fenced code block 语法高亮（highlight.js）与 `$...$` / `$$...$$` 公式渲染（KaTeX auto-render）。

## 2026-06-25 Phase C P2：控制台侧边栏设备状态

- 新增 `chat-web/js/sidebar-devices.js`：登录后从 `/device/v1/app/devices` 拉取已绑定设备，轮询 `/devices/{id}/status` 刷新在线/离线/运行中状态。
- `index.html` 侧边栏新增「我的设备」区，点击跳转设备管理页。

## 2026-06-25 Phase B P1：设备管理页

- 新增 `chat-web/devices.html` + `js/devices.js`：已绑定设备列表、详情抽屉、实时 WebSocket 状态、添加/解绑设备。
- 复用已有后端 `/device/v1/app/devices`、`/device/v1/app/devices/{id}/status`、`/device/v1/app/devices/{id}/ws`、`/device/v1/app/tasks`。
- 同步 `index.html`、`keys.html`、`usage.html` 侧边栏入口。

## 2026-06-25 Phase B P1：用量统计页

- 新增 `/device/v1/app/stats/usage?days=30`：按已完成任务估算每日 Token 消耗、请求次数、费用明细与能力分布。
- 新增 `chat-web/usage.html` + `js/usage.js`：ECharts 暗色主题折线图、柱状图、饼图与分页明细表格。
- 时间范围支持 7/30/90 天切换。

## 2026-06-25 Phase B P1：API Key 管理页

- 新增 `v2_api_key` 表与 `device_logic/api_key.py`，用于生成、列表与软删除用户 API Key。
- 新增 `/device/v1/app/keys`（创建/列表）与 `/device/v1/app/keys/{id}`（删除）。
- 新增 `chat-web/keys.html` + `js/keys.js`：创建 Key 时仅显示一次完整密钥、复制按钮、前缀列表、删除确认。
- 未登录用户访问 `keys.html` 自动跳转登录页。

## 2026-06-25 Phase B P1：控制台登录/注册

- `v2_account` 新增 `email` 字段，支持邮箱/密码注册与 JWT 登录。
- 新增 `/device/v1/app/auth/register-email` 与 `/device/v1/app/auth/login-email`。
- 新增 `chat-web/login.html` 与 `chat-web/register.html`，登录后进入控制台。

## 2026-06-25 Phase C P2：OpenAPI / Redoc 参考页

- 新增 `docs-site/api/reference.md`：从 `openapi.yaml` 自动渲染交互式 API 文档。
- 使用 Redoc 2.1.5，三栏布局，含端点导航、请求/响应示例与代码片段。
- 适配暗色主题与中文文档站风格，线上地址：`https://www.donglicao.com/docs/api/reference.html`。

## 2026-06-25 Phase B P1：产品独立详情页

- 新增 AI 绘图机、AI 写字机、2D 数字人三个产品详情页。
- 每页包含 Hero、功能特性、技术规格、使用场景、FAQ 与 CTA。
- 官网导航增加「产品」下拉菜单，页脚同步更新产品入口。

## 2026-06-25 Phase C P2：API Playground 上线

- 新增 `chat-web/playground.html`：基于 Monaco Editor 与 ECharts 的在线 API 请求调试工具。
- 支持 OpenAI 兼容 Chat Completions、模型选择、流式响应、cURL 复制与本地历史记录。
- 线上地址：`https://chat.donglicao.com/chat/playground.html`。

## 2026-06-25 Phase B P0：管理控制台增强

- 修复 `/admin/api/devices`：新增 `device_gateway/registry.py`，设备列表/详情/重启指令落地到 `v2_device` 表。
- 新增 admin 邮箱/密码 JWT 登录（`/admin/v1/auth/login`），现有 `/admin/*` 同时兼容静态 token。
- API Key 管理补充 per-key 用量查询；`/admin/api/stats` 返回 key 用量摘要。

## 2026-06-25 Phase A P0：官网与开发者体验改进

- 官网新增[定价页](https://www.donglicao.com/pricing.html)四档定价卡片。
- 首页开发者区新增 Python / cURL / JavaScript / Go 多语言代码 Tab。
- FAQ 从 4 条扩展到 12 条，并新增 `FAQPage` JSON-LD。
- Footer 补完社媒入口、ICP 备案号、产品/法律链接。
- 新增 VitePress 开发者文档站：`https://www.donglicao.com/docs/`。
- 生成 `docs/openapi.yaml` 公开 API 规范。

## 2026-06-25 [Phase 5：小程序 P1/P2 增强（M3-M10）](./2026-06-25-phase5.md)

- 完成设备 App 小程序 M3-M10 增强，包括聊天历史、实时状态、语音任务审批、家庭成员、设备共享、素材库、批量绘图等能力。
- 修复 Phase 5 全量 pytest 中的失败用例，测试通过。
- 新增/更新设备开发者文档与发布证据。

## 2026-06-24 [编码能力退役](./2026-06-24-coding-retirement.md)

- 完成编码辅助能力的退役与清理。
- 移除代码编辑、IDE 插件相关路由与入口。
- 路由分类器不再将请求导向编码场景，专注聊天、图像、设备控制。

## 2026-06-24 LiMa 品牌升级为「LiMa 量子星云系统」

- 官网 `donglicao-site` 与 `chat-web` 完成视觉重塑。
- 引入星云暗色主题与青紫渐变品牌色。
- 部署上线并通过公网健康验证。

## 2026-06-24 AI→Motion 阶段 5 发布门追踪

- 新增终端回放与发布门追踪能力。
- 完善 `device_gateway` 过度拆分模块合并。
- 记录发布证据到 `docs/release_evidence/`。

## 更早

详见 `progress.md` 与 `findings.md`。
