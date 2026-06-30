# LiMa chat-web 迁移到 Cloudflare Pages 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `chat-web` 从阿里云 VPS 迁移到 Cloudflare Pages，使用独立域名 `app.donglicao.com`，并把 API/WebSocket 调用指回 `chat.donglicao.com`。

**Architecture:**
- 新增 `chat-web/js/config.js` 集中声明 `apiOrigin` 与 `wsOrigin`。
- 用一个范围有限的 fetch/WebSocket 拦截器把 `/v1/*`、`/device/v1/*`、`/api/*` 相对请求重定向到 `chat.donglicao.com`，避免逐文件改写所有 API 调用。
- 仅对构造完整 URL 的地方（`js/devices.js`、`js/playground-utils.js`、`voice-call.html`）做显式修改。

**Tech Stack:** 原生 HTML/JS, Cloudflare Pages, wrangler-action, GitHub Actions

---

## 文件结构

| 文件 | 职责 |
|---|---|
| `chat-web/js/config.js` | 新建：API/WS 源站配置 + 有限范围 fetch/WebSocket 拦截 |
| `chat-web/js/devices.js` | 修改：WebSocket base 改用 `LIMA_CONFIG.wsOrigin` |
| `chat-web/js/playground-utils.js` | 修改：curl URL 改用 `LIMA_CONFIG.apiOrigin` |
| `chat-web/voice-call.html` | 修改：加载 config.js，WS URL 改用 config |
| `chat-web/index.html` | 修改：CSP 加入 `https://chat.donglicao.com`，加载 config.js |
| `chat-web/login.html` 等 | 修改：加载 config.js |
| `.github/workflows/deploy-chat-web.yml` | 新建：部署到 Cloudflare Pages |
| `.github/workflows/deploy.yml` | 修改：移除 chat-web 部署步骤 |
| 京东云 `/opt/lima-router/.env` | 修改：显式配置 `LIMA_CORS_ORIGINS` |
| 阿里云 `/var/www/chat` | 清理：迁移后删除 |

---

## 前置条件

- `docs-site` 与 `donglicao-site-v2` 已迁移并稳定运行。
- GitHub secrets 已配置：`CLOUDFLARE_ACCOUNT_ID`、`CLOUDFLARE_API_TOKEN`。
- 已创建 Pages project `lima-chat-web`，DNS `app.donglicao.com` CNAME 已准备（先不代理）。

---

### Task 1: 创建 Cloudflare Pages 项目

**Files:**
- Cloudflare Dashboard 操作

- [ ] **Step 1: 创建 Pages project**

  在 Cloudflare Dashboard → Workers & Pages → Create application → Pages → Upload assets，创建 project `lima-chat-web`，记下子域名（默认 `lima-chat-web.pages.dev`）。

- [ ] **Step 2: 准备 DNS 记录**

  Cloudflare DNS 中添加：
  - Name: `app`
  - Target: `lima-chat-web.pages.dev`
  - Proxy status: 已代理（橙色云）
  - TTL: Auto

---

### Task 2: 新增 chat-web 跨域配置

**Files:**
- Create: `chat-web/js/config.js`

- [ ] **Step 1: 创建 `chat-web/js/config.js`**

  ```js
  (function () {
    "use strict";

    window.LIMA_CONFIG = {
      apiOrigin: "https://chat.donglicao.com",
      wsOrigin: "wss://chat.donglicao.com",
    };

    // ponytail: 当 chat-web 托管在 app.donglicao.com 时，把相对 API 路径重定向到
    // 主 API 源站。拦截范围限定为 /v1/*、/device/v1/*、/api/*；若后续增加非 API
    // 的相对路径 fetch，需改为显式前缀或扩展白名单。升级路径：所有调用改为显式
    // window.LIMA_CONFIG.apiOrigin 前缀后移除拦截器。
    if (location.host === "chat.donglicao.com") return;

    const API_PREFIXES = ["/v1/", "/device/v1/", "/api/"];

    const originalFetch = window.fetch;
    window.fetch = function (input, init) {
      if (typeof input === "string" && API_PREFIXES.some((p) => input.startsWith(p))) {
        input = window.LIMA_CONFIG.apiOrigin + input;
      }
      return originalFetch(input, init);
    };

    const OriginalWebSocket = window.WebSocket;
    window.WebSocket = function (url, protocols) {
      if (typeof url === "string" && url.startsWith("/device/v1/")) {
        url = window.LIMA_CONFIG.wsOrigin + url;
      }
      return new OriginalWebSocket(url, protocols);
    };
  })();
  ```

- [ ] **Step 2: 提交 config.js**

  ```bash
  git add chat-web/js/config.js
  git commit -m "feat(chat-web): add cross-origin API config for Pages deployment"
  ```

---

### Task 3: 在 HTML 中加载 config.js

**Files:**
- Modify: `chat-web/index.html`, `chat-web/login.html`, `chat-web/register.html`, `chat-web/keys.html`, `chat-web/usage.html`, `chat-web/devices.html`, `chat-web/playground.html`, `chat-web/handwriting.html`, `chat-web/voice-call.html`

规则：在每个 HTML 的 **第一个 `<script>`** 标签之前加入：

```html
<script src="js/config.js?v=taste3"></script>
```

- [ ] **Step 1: `chat-web/index.html`**

  找到：
  ```html
    <script src="js/api.js?v=taste3"></script>
  ```
  替换为：
  ```html
    <script src="js/config.js?v=taste3"></script>
    <script src="js/api.js?v=taste3"></script>
  ```

- [ ] **Step 2: `chat-web/login.html`**

  找到：
  ```html
    <script src="js/api.js?v=taste3"></script>
  ```
  替换为：
  ```html
    <script src="js/config.js?v=taste3"></script>
    <script src="js/api.js?v=taste3"></script>
  ```

- [ ] **Step 3: `chat-web/register.html`**

  同上。

- [ ] **Step 4: `chat-web/keys.html`**

  同上。

- [ ] **Step 5: `chat-web/usage.html`**

  找到：
  ```html
    <script src="js/api.js?v=taste3"></script>
  ```
  替换为：
  ```html
    <script src="js/config.js?v=taste3"></script>
    <script src="js/api.js?v=taste3"></script>
  ```

- [ ] **Step 6: `chat-web/devices.html`**

  同上。

- [ ] **Step 7: `chat-web/playground.html`**

  找到：
  ```html
    <script src="js/playground-utils.js?v=1"></script>
  ```
  替换为：
  ```html
    <script src="js/config.js?v=taste3"></script>
    <script src="js/playground-utils.js?v=1"></script>
  ```

- [ ] **Step 8: `chat-web/handwriting.html`**

  找到：
  ```html
    <script src="js/api.js?v=taste3"></script>
  ```
  替换为：
  ```html
    <script src="js/config.js?v=taste3"></script>
    <script src="js/api.js?v=taste3"></script>
  ```

- [ ] **Step 9: `chat-web/voice-call.html`**

  找到第一个 `<script>`（约第 205 行）：
  ```html
  <script>
  ```
  替换为：
  ```html
  <script src="js/config.js?v=taste3"></script>
  <script>
  ```

- [ ] **Step 10: 提交 HTML 改动**

  ```bash
  git add chat-web/*.html
  git commit -m "feat(chat-web): load config.js before app scripts"
  ```

---

### Task 4: 修复显式构造的完整 URL

**Files:**
- Modify: `chat-web/js/devices.js`, `chat-web/js/playground-utils.js`, `chat-web/voice-call.html`

- [ ] **Step 1: `chat-web/js/devices.js`**

  找到：
  ```js
  const WS_BASE = (location.protocol === "https:" ? "wss://" : "ws://") + location.host;
  ```
  替换为：
  ```js
  const WS_BASE = window.LIMA_CONFIG.wsOrigin;
  ```

- [ ] **Step 2: `chat-web/js/playground-utils.js`**

  找到：
  ```js
    const url = global.location.origin + "/v1/chat/completions";
  ```
  替换为：
  ```js
    const url = window.LIMA_CONFIG.apiOrigin + "/v1/chat/completions";
  ```

- [ ] **Step 3: `chat-web/voice-call.html`（Gemini 模式）**

  找到：
  ```js
        const base=cfg.url.startsWith('/')?window.location.host+cfg.url:cfg.url;
  ```
  替换为：
  ```js
        const base=cfg.url.startsWith('/')?window.LIMA_CONFIG.wsOrigin.replace(/^wss?:\/\//,'')+cfg.url:cfg.url;
  ```

- [ ] **Step 4: `chat-web/voice-call.html`（本地语音模式）**

  找到：
  ```js
      const proto=window.location.protocol==='https:'?'wss:':'ws:';
      const wsUrl=proto+'//'+window.location.host+'/v1/voice'+'?ticket='+encodeURIComponent(ticket);
  ```
  替换为：
  ```js
      const wsUrl=window.LIMA_CONFIG.wsOrigin+'/v1/voice'+'?ticket='+encodeURIComponent(ticket);
  ```

- [ ] **Step 5: 提交改动**

  ```bash
  git add chat-web/js/devices.js chat-web/js/playground-utils.js chat-web/voice-call.html
  git commit -m "feat(chat-web): route explicit WS/API URLs through LIMA_CONFIG"
  ```

---

### Task 5: 更新 CSP

**Files:**
- Modify: `chat-web/index.html`

- [ ] **Step 1: 扩展 connect-src 与 img-src**

  找到：
  ```html
  <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https://image.pollinations.ai https://chat.donglicao.com https://api.donglicao.com; media-src 'self'; connect-src 'self'; font-src 'self' https://cdn.jsdelivr.net; upgrade-insecure-requests;">
  ```
  替换为：
  ```html
  <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https://image.pollinations.ai https://chat.donglicao.com https://api.donglicao.com; media-src 'self'; connect-src 'self' https://chat.donglicao.com https://api.donglicao.com; font-src 'self' https://cdn.jsdelivr.net; upgrade-insecure-requests;">
  ```

- [ ] **Step 2: 提交**

  ```bash
  git add chat-web/index.html
  git commit -m "feat(chat-web): allow cross-origin API in CSP"
  ```

---

### Task 6: 新增 chat-web Pages 部署 workflow

**Files:**
- Create: `.github/workflows/deploy-chat-web.yml`

- [ ] **Step 1: 创建 workflow 文件**

  ```yaml
  name: Deploy Chat Web

  on:
    push:
      branches: [main]
      paths:
        - "chat-web/**"
        - ".github/workflows/deploy-chat-web.yml"
    workflow_dispatch:

  concurrency:
    group: deploy-chat-web
    cancel-in-progress: false

  jobs:
    deploy:
      runs-on: ubuntu-latest
      env:
        CLOUDFLARE_ACCOUNT_ID: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
        CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}
      steps:
        - uses: actions/checkout@v7

        - name: Deploy to Cloudflare Pages
          uses: cloudflare/wrangler-action@v3
          with:
            apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}
            accountId: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
            command: pages deploy chat-web --project-name=lima-chat-web --branch=main

        - name: Smoke test (Pages dev domain)
          run: |
            sleep 10
            curl -sf https://lima-chat-web.pages.dev/login.html -o /dev/null
            echo "chat-web Pages deploy OK"
  ```

- [ ] **Step 2: 验证 YAML 语法**

  ```bash
  python -c "import yaml; yaml.safe_load(open('.github/workflows/deploy-chat-web.yml'))"
  ```

- [ ] **Step 3: 提交**

  ```bash
  git add .github/workflows/deploy-chat-web.yml
  git commit -m "ci(chat-web): deploy chat-web to Cloudflare Pages"
  ```

---

### Task 7: 从主部署 workflow 中移除 chat-web 步骤

**Files:**
- Modify: `.github/workflows/deploy.yml`

- [ ] **Step 1: 删除 chat-web 部署 job**

  找到并删除以下整个 step（约第 72-77 行）：

  ```yaml
      - name: Deploy Chat Web static files
        if: env.VPS_SSH_KEY_SET == 'true' && env.VPS_HOST_SET == 'true'
        timeout-minutes: 5
        env:
          LIMA_DEPLOY_HOST: root@${{ secrets.VPS_HOST }}
        run: python scripts/deploy_chat_web.py
  ```

- [ ] **Step 2: 提交**

  ```bash
  git add .github/workflows/deploy.yml
  git commit -m "ci(deploy): remove chat-web deploy from core workflow"
  ```

---

### Task 8: 配置 LiMa 服务端 CORS

**Files:**
- 京东云 VPS `/opt/lima-router/.env`

- [ ] **Step 1: 追加 CORS 配置**

  SSH 到京东云，先备份：
  ```bash
  cp /opt/lima-router/.env /opt/lima-router/.env.bak.chatweb.$(date +%Y%m%d%H%M%S)
  ```

  然后追加（不覆盖原文件）：
  ```bash
  echo 'LIMA_CORS_ORIGINS=https://app.donglicao.com,https://chat.donglicao.com' >> /opt/lima-router/.env
  ```

- [ ] **Step 2: 重启 lima-router**

  ```bash
  systemctl restart lima-router
  systemctl status lima-router --no-pager
  ```
  预期：`active (running)`。

---

### Task 9: 部署 chat-web 到 Pages

**Files:**
- GitHub Actions 触发

- [ ] **Step 1: push 代码触发 workflow**

  确保前面所有 commit 已 push 到 `main`。

- [ ] **Step 2: 检查 Pages dev 域名**

  ```bash
  curl -sf https://lima-chat-web.pages.dev/login.html -o /dev/null && echo OK
  ```
  预期：输出 `OK`。

---

### Task 10: 切换 DNS 并验证

**Files:**
- Cloudflare Dashboard 操作

- [ ] **Step 1: 启用 `app.donglicao.com` CNAME 代理**

  确认 Cloudflare DNS 中 `app.donglicao.com` CNAME → `lima-chat-web.pages.dev` 已代理。

- [ ] **Step 2: 验证自定义域名**

  ```bash
  for i in {1..12}; do
    curl -sf https://app.donglicao.com/login.html -o /dev/null && echo "OK" && break
    echo "retry $i..."
    sleep 10
  done
  ```
  预期：输出 `OK`。

- [ ] **Step 3: 端到端聊天验证**

  浏览器打开 `https://app.donglicao.com/`，完成一次匿名/登录对话，确认：
  - `POST https://chat.donglicao.com/v1/chat/completions` 返回 200。
  - 设备 WS ticket 获取与连接正常（如已登录且有设备）。

---

### Task 11: 清理阿里云 chat-web 静态文件

**Files:**
- 阿里云 VPS 远程操作

- [ ] **Step 1: 备份并删除 `/var/www/chat`**

  ```bash
  sudo cp -a /var/www/chat /var/www/chat.bak.$(date +%Y%m%d%H%M%S)
  sudo rm -rf /var/www/chat
  ```

- [ ] **Step 2: 清理 nginx 中的 chat-web 静态配置**

  编辑 `/etc/nginx/sites-available/chat.donglicao.com.conf`，删除或注释所有仅用于服务 chat-web 静态文件的 `location` 与 `root` 配置，保留 API 反向代理部分（当前为 `proxy_pass http://127.0.0.1:8080` 作为回滚备用）。

  然后：
  ```bash
  sudo nginx -t && sudo systemctl reload nginx
  ```

- [ ] **Step 3: 验证清理**

  ```bash
  ls /var/www/chat
  ```
  预期：目录不存在。

---

### Task 12: 记录 ponytail 债务

**Files:**
- Create/append: `PONYTAIL-DEBT.md`（如不存在则新建）

- [ ] **Step 1: 添加债务条目**

  ```markdown
  ## 2026-06-30 chat-web 跨域 fetch/WebSocket 拦截器

  - **位置**: `chat-web/js/config.js`
  - ** shortcut**: 用全局 fetch/WebSocket 拦截器把相对 API 路径重定向到 `chat.donglicao.com`。
  - **已知上限**: 仅匹配 `/v1/`、`/device/v1/`、`/api/` 前缀；若后续增加非 API 相对路径 fetch 会被误改。全局 monkey-patch 也可能影响未来引入的第三方库。
  - **升级路径**: 所有 API/WS 调用改为显式使用 `window.LIMA_CONFIG.apiOrigin` / `wsOrigin` 前缀后，移除拦截器。
  ```

- [ ] **Step 2: 提交**

  ```bash
  git add PONYTAIL-DEBT.md
  git commit -m "docs: record chat-web cross-origin interceptor debt"
  ```

---

## 验收标准

- `https://app.donglicao.com/login.html` 200。
- 从 `app.donglicao.com` 发起聊天，`POST https://chat.donglicao.com/v1/chat/completions` 200。
- 设备 WS 连接正常（Phase 3 高优先级验证项）。
- GitHub Actions `Deploy Chat Web` 成功运行。
- 阿里云 `/var/www/chat` 已删除。
- `.github/workflows/deploy.yml` 中不再包含 chat-web 部署步骤。
- 京东云 `.env` 包含 `LIMA_CORS_ORIGINS=https://app.donglicao.com,https://chat.donglicao.com`。
