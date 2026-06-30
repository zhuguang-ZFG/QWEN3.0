# LiMa 官网 (donglicao-site-v2) 迁移到 Cloudflare Pages 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `donglicao-site-v2` 从阿里云 VPS 部署改到 Cloudflare Pages，域名 `www.donglicao.com`。

**Architecture:** 使用 GitHub Actions 构建 Next.js static export，再用 `cloudflare/wrangler-action@v3` 直接上传到 Cloudflare Pages。

**Tech Stack:** Next.js 15, Cloudflare Pages, wrangler-action, GitHub Actions

---

## 文件结构

| 文件 | 职责 |
|---|---|
| `.github/workflows/deploy-site-v2.yml` | GitHub Actions workflow：构建 + 部署到 Pages |
| `donglicao-site-v2/next.config.ts` | 已配置 `output: "export"` 和 `distDir: "dist"` |
| `donglicao-site-v2/dist/` | Next.js 静态导出产物（临时，不提交） |
| 阿里云 VPS 上的 `secrets.SITE_V2_DIR` 目录 | 迁移后删除 |

---

## 前置条件

- `docs-site` 已成功迁移并验证（推荐顺序）。
- GitHub secrets 已配置：`CLOUDFLARE_ACCOUNT_ID`、`CLOUDFLARE_API_TOKEN`。

---

### Task 1: 创建 Cloudflare Pages 项目

**Files:**
- Cloudflare Dashboard 操作

- [ ] **Step 1: 在 Cloudflare Dashboard 创建 Pages 项目**

  路径：Workers & Pages → Create application → Pages → Upload assets.
  Project name填 `lima-www`，记下 Pages 子域名（默认 `lima-www.pages.dev`）。

- [ ] **Step 2: 准备 DNS 记录**

  在 Cloudflare DNS 中为 `www.donglicao.com` 添加 CNAME：
  - Name: `www`
  - Target: `lima-www.pages.dev`
  - Proxy status: 已代理（橙色云）
  - TTL: Auto

---

### Task 2: 改造 GitHub Actions workflow

**Files:**
- Modify: `.github/workflows/deploy-site-v2.yml`

- [ ] **Step 1: 用 wrangler-action 替换 SCP/SSH**

  将 `.github/workflows/deploy-site-v2.yml` 完整替换为：

  ```yaml
  name: Deploy Next.js Site

  on:
    push:
      branches: [main]
      paths:
        - "donglicao-site-v2/**"
        - ".github/workflows/deploy-site-v2.yml"
    workflow_dispatch:

  concurrency:
    group: deploy-site-v2
    cancel-in-progress: false

  jobs:
    build-and-deploy:
      runs-on: ubuntu-latest
      env:
        CLOUDFLARE_ACCOUNT_ID: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
        CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}
      steps:
        - uses: actions/checkout@v7

        - name: Set up Node.js
          uses: actions/setup-node@v4
          with:
            node-version: 24

        - name: Impeccable design check
          working-directory: donglicao-site-v2
          run: npx impeccable@latest detect .

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

        - name: Smoke test (Pages dev domain)
          run: |
            sleep 10
            curl -sf https://lima-www.pages.dev/ -o /dev/null
            echo "site-v2 Pages deploy OK"
  ```

- [ ] **Step 2: 本地验证 YAML 语法**

  ```bash
  python -c "import yaml; yaml.safe_load(open('.github/workflows/deploy-site-v2.yml'))"
  ```
  预期：无报错。

- [ ] **Step 3: 提交 workflow 改动**

  ```bash
  git add .github/workflows/deploy-site-v2.yml
  git commit -m "ci(site): deploy donglicao-site-v2 to Cloudflare Pages"
  ```

---

### Task 3: 触发首次部署并验证

**Files:**
- 无代码文件

- [ ] **Step 1: 手动触发 workflow**

  在 GitHub Actions 页面选择 `Deploy Next.js Site` → `Run workflow` → `main`。

- [ ] **Step 2: 检查 Pages dev 域名**

  ```bash
  curl -sf https://lima-www.pages.dev/ -o /dev/null && echo OK
  curl -sf https://lima-www.pages.dev/en/ -o /dev/null && echo EN_OK
  ```
  预期：均输出 `OK` / `EN_OK`。

---

### Task 4: 切换 DNS 并验证

**Files:**
- Cloudflare Dashboard 操作

- [ ] **Step 1: 启用 `www.donglicao.com` CNAME 代理**

  确保 `www.donglicao.com` CNAME → `lima-www.pages.dev` 且代理状态为 **已代理**。

- [ ] **Step 2: 验证自定义域名**

  ```bash
  for i in {1..12}; do
    curl -sf https://www.donglicao.com/ -o /dev/null && echo "OK" && break
    echo "retry $i..."
    sleep 10
  done
  ```
  预期：输出 `OK`。

---

### Task 5: 清理阿里云 VPS 上的官网静态文件

**Files:**
- 阿里云 VPS 远程操作

- [ ] **Step 1: 备份并删除 site-v2 目录**

  SSH 到阿里云 VPS，执行（将 `<SITE_V2_DIR>` 替换为实际路径，如 `/var/www/www`）：
  ```bash
  sudo cp -a <SITE_V2_DIR> <SITE_V2_DIR>.bak.$(date +%Y%m%d%H%M%S)
  sudo rm -rf <SITE_V2_DIR>
  ```

- [ ] **Step 2: 移除官网 nginx server block**

  ```bash
  sudo rm -f /etc/nginx/sites-enabled/www.donglicao.com.conf
  sudo rm -f /etc/nginx/sites-available/www.donglicao.com.conf
  sudo nginx -t && sudo systemctl reload nginx
  ```

- [ ] **Step 3: 验证清理**

  ```bash
  ls <SITE_V2_DIR>
  ```
  预期：目录不存在。

---

## 验收标准

- `https://www.donglicao.com/` 200，首页、英文站 `/en/`、博客页均正常。
- GitHub Actions `Deploy Next.js Site` 成功运行。
- 阿里云 VPS 上不再存放 `donglicao-site-v2` 构建产物。
- 回滚路径可用：将 DNS CNAME 改回阿里云源站即可恢复。
