# LiMa 静态站点迁移到 Cloudflare Pages 设计

> 目标：把 `docs-site`、`donglicao-site-v2`、`chat-web` 从阿里云 VPS 的 nginx 迁到 Cloudflare Pages，减少服务器磁盘、流量和构建负载，并简化 GitHub Actions 部署流程。
> 状态：已批准，待进入 implementation plan。

---

## 1. 背景与现状

LiMa 主计算已迁移到京东云，公网入口通过 Cloudflare Tunnel (`lima-jdcloud`) 直连京东云。阿里云当前仍承担部分静态站点服务：

- `chat-web` 部署在 `/var/www/chat/`，由阿里云 nginx 直接服务，且与 API 共用 `chat.donglicao.com`。
- `donglicao-site-v2`（Next.js 官网）构建后通过 GitHub Actions + `appleboy/scp-action` 推送到阿里云。
- `docs-site`（VitePress 文档站）同样通过 GitHub Actions + SCP 推送到阿里云。

这三个站点均为静态内容，适合迁移到 Cloudflare Pages。

---

## 2. 目标与三阶段范围

| 阶段 | 站点 | 源目录 | 目标域名 | Pages project（建议名） | 风险 |
|---|---|---|---|---|---|
| Phase 1 | `docs-site` | `docs-site/.vitepress/dist` | `docs.donglicao.com` | `lima-docs` | 低，只读文档 |
| Phase 2 | `donglicao-site-v2` | `donglicao-site-v2/dist` | `www.donglicao.com` | `lima-www` | 低，纯静态 |
| Phase 3 | `chat-web` | `chat-web/` | `app.donglicao.com` | `lima-chat-web` | 中，需改动 API/WS 调用路径 |

`chat.donglicao.com` 继续作为 LiMa API 入口，通过 Cloudflare Tunnel 直连京东云，不受本次迁移影响。

---

## 3. 部署方案

### 3.1 Cloudflare 侧准备

1. **创建三个 Pages project**：
   - `lima-docs`
   - `lima-www`
   - `lima-chat-web`
2. **DNS 记录**（在 Cloudflare `donglicao.com` Zone 中配置）：

   | 域名 | 类型 | 值 | 代理状态 |
   |---|---|---|---|
   | `docs.donglicao.com` | CNAME | `<lima-docs>.pages.dev` | 已代理 |
   | `www.donglicao.com` | CNAME | `<lima-www>.pages.dev` | 已代理 |
   | `app.donglicao.com` | CNAME | `<lima-chat-web>.pages.dev` | 已代理 |

3. **API Token**：
   - 使用限定权限的 `CLOUDFLARE_API_TOKEN`。
   - 权限模板：`Zone:DNS:Edit`（仅 `donglicao.com`）+ `Cloudflare Pages:Edit`。
   - 禁止写入 Git；仅通过 GitHub secrets 注入。

### 3.2 GitHub Actions 改造

所有静态站点 workflow 统一使用 `cloudflare/wrangler-action@v3` 部署。

#### docs-site

```yaml
- name: Enable pnpm
  run: corepack enable

- name: Build
  working-directory: docs-site
  run: |
    corepack pnpm install --frozen-lockfile
    corepack pnpm run build

- name: Deploy to Cloudflare Pages
  uses: cloudflare/wrangler-action@v3
  with:
    apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}
    accountId: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
    command: pages deploy docs-site/.vitepress/dist --project-name=lima-docs --branch=main
```

#### donglicao-site-v2

```yaml
- name: Install dependencies and build
  working-directory: donglicao-site-v2
  run: |
    npm ci
    npm run build

- name: Deploy to Cloudflare Pages
  uses: cloudflare/wrangler-action@v3
  with:
    apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}
    accountId: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
    command: pages deploy donglicao-site-v2/dist --project-name=lima-www --branch=main
```

#### chat-web

chat-web 是原生静态文件，无需构建：

```yaml
- name: Deploy to Cloudflare Pages
  uses: cloudflare/wrangler-action@v3
  with:
    apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}
    accountId: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
    command: pages deploy chat-web --project-name=lima-chat-web --branch=main
```

### 3.3 需要新增的 workflow

- 新增 `.github/workflows/deploy-chat-web.yml`（当前 chat-web 在 `.github/workflows/deploy.yml` 中通过 `scripts/deploy_chat_web.py` 部署）。

### 3.4 需要移除/简化的 workflow 步骤

- `.github/workflows/deploy-site-v2.yml`：移除 `appleboy/scp-action` 和 `appleboy/ssh-action` 的 VPS 部署与 nginx reload 步骤。
- `.github/workflows/deploy-docs-site.yml`：同上。
- `.github/workflows/deploy.yml`：当 Phase 3 完成后，移除其中 "Deploy Chat Web static files" job。

---

## 4. chat-web 跨域改造

chat-web 当前使用相对路径调用 API，与 API 同域。迁移到 `app.donglicao.com` 后，必须显式指向 `chat.donglicao.com`。

### 4.1 新增配置

新增 `chat-web/js/config.js`，并在所有使用它的 HTML 中**最先加载**（放在其他 `chat-web/js/*.js` 之前）：

```js
window.LIMA_CONFIG = {
  apiOrigin: "https://chat.donglicao.com",
  wsOrigin: "wss://chat.donglicao.com",
};
```

### 4.2 需要改动的文件

- `chat-web/js/api.js`：所有 `fetch(API_BASE + path)` 改为 `fetch(window.LIMA_CONFIG.apiOrigin + path)`。
- `chat-web/chat-api.js`：`/v1/images/generations` 与 `/v1/chat/completions` 前加 `window.LIMA_CONFIG.apiOrigin`。
- `chat-web/js/model-selector.js`、`chat-web/js/playground.js`、`chat-web/js/playground-utils.js`：`/v1/models`、`/v1/chat/completions` 改前缀。
- `chat-web/js/auth.js`、`chat-web/js/keys.js`、`chat-web/js/usage.js`、`chat-web/js/devices.js`、`chat-web/js/sidebar-devices.js`、`chat-web/js/handwriting.js`、`chat-web/js/asset-upload.js`：`/device/v1/app/...` 路径加前缀。
- `chat-web/js/devices.js`：`WS_BASE` 改为 `window.LIMA_CONFIG.wsOrigin`。
- `chat-web/voice-call.html`：`/api/live-key`、`/v1/voice/ticket`、WebSocket 路径使用 `window.LIMA_CONFIG.apiOrigin`/`wsOrigin`。
- `chat-web/index.html`：CSP 的 `connect-src` 和 `img-src` 加入 `https://chat.donglicao.com`。

### 4.3 服务端 CORS

LiMa 服务端默认 `LIMA_CORS_ORIGINS=*`，但为了安全，建议在京东云 `.env` 中显式配置并重启 `lima-router`：

```env
LIMA_CORS_ORIGINS=https://app.donglicao.com,https://chat.donglicao.com
```

---

## 5. VPS 清理

每阶段验证无误后，在阿里云执行清理：

1. 删除对应 `/var/www/<site>` 目录（保留一次带时间戳的备份）。
2. 注释/删除对应 nginx server block：
   - docs 与官网的独立 server block 直接删除。
   - `chat.donglicao.com.conf` 中静态根目录配置可改为仅保留 API 反向代理；如不再本地服务 chat-web，可移除 `/var/www/chat` 相关 location。
3. 停止为该站点在 VPS 上安装 Node.js 依赖和构建。
4. 执行 `nginx -t && systemctl reload nginx`。

最终目标：阿里云不再为静态站点提供文件服务，只保留：
- 应急回滚能力（备份与简化版 nginx 配置）。
- 必要时的反向代理配置（当前已还原为本地 `127.0.0.1:8080` 备用）。

---

## 6. 验证与验收标准

每阶段部署后执行：

- HTTPS 200：对应域名首页可访问，无混合内容警告。
- 关键路径可访问：
  - `docs.donglicao.com` 文档首页。
  - `www.donglicao.com` 官网首页、`/en/`、博客页。
  - `app.donglicao.com` 登录页、聊天页。
- chat-web 端到端（Phase 3）：
  - 匿名/登录后发起对话，`POST https://chat.donglicao.com/v1/chat/completions` 返回 200。
  - 设备 WS ticket 获取与连接正常。
- GitHub Actions 部署 job 成功，无 secret 泄露。

---

## 7. 回滚方案

| 场景 | 操作 |
|---|---|
| Pages 部署失败 | 不切换 DNS，保留现有 VPS 服务 |
| DNS 切换后异常 | 在 Cloudflare DNS 把对应 CNAME 改回阿里云源站（A 记录或原 CNAME），并恢复 nginx 配置 |
| chat-web API 跨域异常 | 把 `app.donglicao.com` DNS 改回 VPS，同时回滚 `chat-web/js/config.js` 改动 |

---

## 8. 资源节省预期

- **阿里云 VPS**：
  - 释放 `/var/www/chat`、`donglicao-site-v2/dist`、`docs-site/.vitepress/dist` 占用的磁盘。
  - 减少静态文件出站流量。
  - 移除 Next.js/VitePress 在 VPS 上的构建依赖（构建改在 GitHub Actions 或 Cloudflare Pages 构建环境中完成）。
- **GitHub Actions**：
  - 去掉 SSH/SCP 步骤，减少 workflow 执行时间。
  - 去掉 `appleboy/scp-action`、`appleboy/ssh-action` 的使用。
  - 后续如想进一步节省 runner 时间，可将 site/docs 切到 Cloudflare Pages 原生 Git 集成，完全移除对应 workflow。

---

## 9. 风险与注意事项

- **chat-web 路径改动面最大**：多个 JS/HTML 文件使用相对路径，需完整回归测试。
- **Cloudflare Pages 限制**：免费版单次构建 20 分钟、产物 500 MB，本次站点均远低于限制。
- **DNS 传播**：Cloudflare 通常秒级，但建议低峰期切换并保留回滚路径。
- **SEO/Canonical**：官网和文档站现有 `canonical`/`hreflang` 配置保持不变，切换域名后搜索引擎会跟随 DNS。
- **凭证安全**：`CLOUDFLARE_API_TOKEN` 仅授予 Pages 与 DNS 编辑权限，不写入仓库，仅通过 GitHub secrets 注入。

---

## 10. 后续可选优化

- 为 `app.donglicao.com` 开启 Cloudflare Pages Functions 或 Workers，实现边缘侧的轻量路由/缓存。
- 将 `chat-web` 的静态资源长期缓存策略交给 Cloudflare CDN，减少回源。
- 当所有静态站稳定运行在 Pages 后，评估是否关闭阿里云的 nginx 备用实例，进一步节省服务器资源。
