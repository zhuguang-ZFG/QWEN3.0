# 阿里云 pilot 流量分流方案

> 目标：让 `chat.donglicao.com` 的部分简单匿名聊天请求由阿里云 `lima-router-pilot`（仅免费后端）处理，降低京东云主节点负载。
> 决策：前端按模型/场景主动选择 endpoint；Cloudflare Worker 作为可选兜底/灰度能力。
> 状态：计划待审批

---

## 1. 目标

- 将适合免费后端的请求（匿名、简单 chat、无工具/无图片/无复杂模型指定）导向 `https://aliyun.donglicao.com/v1/chat/completions`。
- 京东云主节点继续承载：认证用户、IDE/编码请求、vision、image generation、device gateway、需要 session_memory 的请求。
- 不改动现有 `chat.donglicao.com` 的 DNS/Tunnel 架构；分流通过前端代码实现，Worker 仅作补充。

## 2. 非目标

- 不替换 Cloudflare Tunnel 或京东云主入口。
- 不修改 `router_v3/select.py` 的免费后端池过滤逻辑（已上线）。
- 不在边缘做复杂 body 解析或模型级路由（避免 Worker 读取/缓存请求体）。
- 不要求 pilot 支持设备网关、session memory、MQTT、图片生成、vision。

## 3. 分流规则（前端决定）

满足**全部**以下条件时，请求发送到阿里云 pilot：

1. 当前页面在 `chat.donglicao.com` 域（同源或显式选择 pilot）。
2. 未设置 API Key（匿名用户）。
3. 请求类型为普通 chat（`model` 为默认 `lima`/`lima-1.3`，无 `tools`、`tool_choice`、`image_url`）。
4. 非 `/image` 图片生成、非 `/v1/images/generations`。
5. 非设备相关 API（`/device/v1/*`）。

否则仍使用 `https://chat.donglicao.com`。

## 4. 需要改动的文件

### 前端：chat-web（主入口）

| 文件 | 改动 |
|---|---|
| `chat-web/js/app-config.js`（新增） | 暴露 `getApiOrigin()`：根据当前 key、请求路径、是否匿名返回 `chat.donglicao.com` 或 `aliyun.donglicao.com`。 |
| `chat-web/chat-api.js` | `sendMessage()` 与 `generateImage()` 使用 `getApiOrigin()` 拼接完整 URL；`/image` 仍走主节点。 |
| `chat-web/js/api.js` | `LiMaAPI` 的 `post/get/del/put` 支持可选 `baseUrl` 参数，或被 `app-config.js` 全局配置覆盖。 |
| `chat-web/index.html` / `playground.html` / `login.html` 等 | CSP `connect-src` 增加 `https://aliyun.donglicao.com`；API 文档示例可选择 endpoint。 |
| `chat-web/js/playground.js` / `playground-utils.js` | Playground 的 curl/API 调用根据是否提供 key 自动切换 endpoint。 |

### 前端：manager-mobile（小程序/H5）

| 文件 | 改动 |
|---|---|
| `esp32S_XYZ/server/xiaozhi-esp32-server/main/manager-mobile/src/utils/index.ts` | `getEnvBaseUrl()` 新增场景分支：AI 闲聊/绘画预览走 `aliyun.donglicao.com`；认证/设备/任务走 `chat.donglicao.com`。 |
| `esp32S_XYZ/server/xiaozhi-esp32-server/main/manager-mobile/src/api/chat/chat.ts` | 普通 chat 请求根据 `method.config.meta.pilot` 选择 baseUrl。 |
| `esp32S_XYZ/server/xiaozhi-esp32-server/main/manager-mobile/src/http/request/alova.ts` | 允许 `method.config.meta.domain` 取值为 `aliyun`，并校验仅用于匿名 chat。 |

### 前端：官网 playground

| 文件 | 改动 |
|---|---|
| `donglicao-site-v2/app/login/page.tsx` | 默认 baseUrl 逻辑：未登录时切换到 `aliyun.donglicao.com`。 |
| `donglicao-site-v2/app/developer/playground/page.tsx` | 同上；提供显式 endpoint 选择器。 |
| `donglicao-site-v2/app/components/Developer.tsx` | curl 示例根据 key 是否存在动态显示 endpoint。 |

### 后端

| 文件 | 改动 |
|---|---|
| `server.py` | 无需改动（CORS 默认 `*` 已允许跨域）；若生产 `.env` 显式配置 `LIMA_CORS_ORIGINS`，需在阿里云 pilot `.env` 追加 `chat.donglicao.com`。 |
| `deploy/aliyun/aliyun-pilot.nginx.conf` | 增加 CORS 预检响应头（`Access-Control-Allow-Origin`、`Access-Control-Allow-Methods`、`Access-Control-Allow-Headers`），与 FastAPI CORS 中间件互补。 |
| `access_guard.py` | 确认阿里云 pilot 对匿名请求放行；已在 `LIMA_ALLOW_ANONYMOUS=1` 下验证。 |

### Cloudflare Worker（可选兜底）

| 文件 | 改动 |
|---|---|
| `cloudflare/workers/aliyun-pilot-router.js`（新增） | 部署到 `chat.donglicao.com/*` 的 Worker：对 `/v1/chat/completions` 且**无 `Authorization` 头**、非 `vision`/`tools` 的 POST 请求，透明代理到 `aliyun.donglicao.com`；其余请求回源到 JDCloud tunnel。 |
| `chat-web/_headers` / `donglicao-site-v2/public/_headers` | 如 Worker 返回额外头，确保 CSP 不拦截。 |

## 5. 测试策略

- **单元测试**
  - 新增 `tests/test_pilot_endpoint_selection.py`：验证 `should_use_pilot(request)` 对匿名 chat/有 key/vision/工具/设备请求的判定。
- **前端测试**
  - chat-web：本地修改 host 后，匿名发送简单消息，Network 面板显示请求目标为 `aliyun.donglicao.com`。
  - manager-mobile：H5 构建后，匿名聊天请求 baseUrl 为 `aliyun.donglicao.com`；登录后切回 `chat.donglicao.com`。
- **端到端**
  - `curl -H "Origin: https://chat.donglicao.com" https://aliyun.donglicao.com/v1/chat/completions` 返回 200 且 CORS 头正确。
  - 匿名 chat 在 `aliyun.donglicao.com` 由 `fireworks_qwen_72b`/`google_flash` 等免费后端响应。
  - 带 key 的 chat 仍走 `chat.donglicao.com` 且后端不限于免费池。
  - `/v1/images/generations`、vision chat、`/device/v1/*` 仍走 `chat.donglicao.com`。

## 6. 部署与上线步骤

1. **后端**：确认阿里云 pilot `.env` 包含 `LIMA_ALLOW_ANONYMOUS=1` 且 CORS 允许 `chat.donglicao.com` origin。
2. **nginx**：更新 `aliyun-pilot.nginx.conf` 增加 CORS 头，重载 nginx。
3. **chat-web**：修改 endpoint 选择逻辑，构建/部署到 VPS `/var/www/chat/`。
4. **manager-mobile**：修改 baseUrl 分支，构建 H5 并上传 `/var/www/chat/mobile/`；微信小程序单独发版。
5. **官网**：更新 playground baseUrl 逻辑，部署到 Cloudflare Pages / VPS。
6. **Worker（可选）**：部署透明代理脚本，开启 1% 灰度，监控 5xx/延迟/后端分布。
7. **监控**：对比 `chat.donglicao.com` 与 `aliyun.donglicao.com` 的 RPS、错误率、免费后端可用性。

## 7. 风险与回滚

| 风险 | 影响 | 缓解/回滚 |
|---|---|---|
| 免费后端池耗尽/限速 | pilot 请求失败或响应慢 | 前端检测到 503/429 后自动重试主节点；Worker 灰度比例归零。 |
| CORS 头缺失或 CSP 未更新 | 浏览器跨域请求被拦截 | 本地/预发先用 curl + 浏览器验证；回滚前端静态文件。 |
| 匿名用户实际是付费体验用户 | 被误导到免费后端，体验下降 | 分流规则加“无 key + model=lima-1.3 默认”双重判断；保留设置 key 后走主节点。 |
| Worker 读取请求体导致延迟/计费 | Cloudflare Worker CPU 时间增加 | Worker 只读 headers，不解析 body；超出免费额度时关闭 Worker。 |
| pilot 与主节点状态不同步 | session/memory 不一致 | pilot 已关闭 session_memory；匿名请求无状态，天然安全。 |

## 8. 验收标准

- [ ] 匿名简单 chat 请求至少有 50% 实际命中 `aliyun.donglicao.com`（前端选择 + Worker 兜底）。
- [ ] 带 API Key、vision、image generation、device API 的请求 100% 仍走 `chat.donglicao.com`。
- [ ] `aliyun.donglicao.com` 的 5xx 率 < 1%，P95 延迟 < 主节点 1.5 倍。
- [ ] 全量 pytest / ruff / pyright / check_code_size 通过。
- [ ] 前端 CSP/Security Headers 无回归。

## 9. 建议的首个切片

先只做 **chat-web 的匿名 chat 分流**：

1. 新增 `chat-web/js/app-config.js`。
2. 修改 `chat-web/chat-api.js` 的 `sendMessage()`。
3. 更新 `chat-web/index.html` CSP。
4. 部署到 VPS 并验证匿名请求命中 pilot。

这个切片最小、风险最低、可独立回滚，验证通过后再扩展到 manager-mobile 和官网。
