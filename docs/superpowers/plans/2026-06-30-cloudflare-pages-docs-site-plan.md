# LiMa docs-site 迁移到 Cloudflare Pages 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `docs-site` 从阿里云 VPS 部署改到 Cloudflare Pages，域名 `docs.donglicao.com`。

**Architecture:** 使用 GitHub Actions 构建 VitePress 静态站点，再用 `cloudflare/wrangler-action@v3` 直接上传到 Cloudflare Pages；DNS CNAME 指向 Pages 子域名。

**Tech Stack:** VitePress, Cloudflare Pages, wrangler-action, GitHub Actions

---

## 文件结构

| 文件 | 职责 |
|---|---|
| `.github/workflows/deploy-docs-site.yml` | GitHub Actions workflow：构建 + 部署到 Pages |
| `docs-site/.vitepress/dist/` | VitePress 构建输出（临时产物，不提交） |
| 阿里云 VPS 上的 `secrets.DOCS_SITE_DIR` 目录 | 迁移后删除 |

---

## 前置条件

- Cloudflare 账号已有 `donglicao.com` Zone。
- GitHub 仓库已配置 secrets：`CLOUDFLARE_ACCOUNT_ID`、`CLOUDFLARE_API_TOKEN`（权限：`Zone:DNS:Edit` 仅限 `donglicao.com` + `Cloudflare Pages:Edit`）。

---

### Task 1: 创建 Cloudflare Pages 项目

**Files:**
- Cloudflare Dashboard 操作（无代码文件）

- [ ] **Step 1: 在 Cloudflare Dashboard 创建 Pages 项目**

  路径：Workers & Pages → Create application → Pages → Upload assets.
  Project name填 `lima-docs`，创建成功后记下 Pages 子域名（默认 `lima-docs.pages.dev`）。

- [ ] **Step 2: 添加 DNS 记录（先不切换，仅准备）**

  在 Cloudflare DNS 中为 `docs.donglicao.com` 添加 CNAME：
  - Name: `docs`
  - Target: `lima-docs.pages.dev`
  - Proxy status: 已代理（橙色云）
  - TTL: Auto

  初始状态可保持 **DNS only** 或记录，待首次部署成功后再启用代理。

---

### Task 2: 改造 GitHub Actions workflow

**Files:**
- Modify: `.github/workflows/deploy-docs-site.yml`

- [ ] **Step 1: 用 wrangler-action 替换 SCP/SSH 部署**

  将 `.github/workflows/deploy-docs-site.yml` 完整替换为：

  ```yaml
  name: Deploy Docs Site

  on:
    push:
      branches: [main]
      paths:
        - "docs-site/**"
        - ".github/workflows/deploy-docs-site.yml"
    workflow_dispatch:

  concurrency:
    group: deploy-docs-site
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
            node-version: 22

        - name: Enable pnpm
          run: corepack enable

        - name: Install dependencies and build
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

        - name: Smoke test (Pages dev domain)
          run: |
            sleep 10
            curl -sf https://lima-docs.pages.dev/ -o /dev/null
            echo "docs-site Pages deploy OK"
  ```

- [ ] **Step 2: 本地验证 YAML 语法**

  运行：
  ```bash
  python -c "import yaml; yaml.safe_load(open('.github/workflows/deploy-docs-site.yml'))"
  ```
  预期：无报错。

- [ ] **Step 3: 提交 workflow 改动**

  ```bash
  git add .github/workflows/deploy-docs-site.yml
  git commit -m "ci(docs): deploy docs-site to Cloudflare Pages"
  ```

---

### Task 3: 触发首次部署并验证

**Files:**
- 无代码文件

- [ ] **Step 1: 手动触发 workflow**

  在 GitHub Actions 页面选择 `Deploy Docs Site` → `Run workflow` → `main`，等待完成。

- [ ] **Step 2: 检查部署结果**

  - workflow 全部 job 绿色通过。
  - `https://lima-docs.pages.dev/` 返回 200，页面内容正确。

---

### Task 4: 切换 DNS 到 Cloudflare Pages

**Files:**
- Cloudflare Dashboard 操作

- [ ] **Step 1: 启用/确认 `docs.donglicao.com` CNAME**

  确保 Cloudflare DNS 中：
  - `docs.donglicao.com` CNAME → `lima-docs.pages.dev`
  - 代理状态为 **已代理**（橙色云）

- [ ] **Step 2: 等待并验证自定义域名**

  运行：
  ```bash
  for i in {1..12}; do
    curl -sf https://docs.donglicao.com/ -o /dev/null && echo "OK" && break
    echo "retry $i..."
    sleep 10
  done
  ```
  预期：某次重试输出 `OK`。

---

### Task 5: 清理阿里云 VPS 上的 docs-site 静态文件

**Files:**
- 阿里云 VPS 远程操作

- [ ] **Step 1: 备份并删除 docs-site 目录**

  SSH 到阿里云 VPS，执行（将 `<DOCS_SITE_DIR>` 替换为实际路径，如 `/var/www/docs`）：
  ```bash
  sudo cp -a <DOCS_SITE_DIR> <DOCS_SITE_DIR>.bak.$(date +%Y%m%d%H%M%S)
  sudo rm -rf <DOCS_SITE_DIR>
  ```

- [ ] **Step 2: 移除 docs-site nginx server block**

  ```bash
  sudo rm -f /etc/nginx/sites-enabled/docs.donglicao.com.conf
  sudo rm -f /etc/nginx/sites-available/docs.donglicao.com.conf
  sudo nginx -t && sudo systemctl reload nginx
  ```

- [ ] **Step 3: 验证清理**

  ```bash
  ls <DOCS_SITE_DIR>
  ```
  预期：目录不存在。

---

## 验收标准

- `https://docs.donglicao.com/` 200，内容正确。
- GitHub Actions `Deploy Docs Site` 成功运行。
- 阿里云 VPS 上不再存放 docs-site 构建产物。
- 回滚路径可用：将 DNS CNAME 改回阿里云源站即可恢复。
