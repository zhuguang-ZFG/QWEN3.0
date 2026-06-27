# LiMa 自动部署与发布约定

> 更新日期：2026-06-26
> 权威文档。CLAUDE.md / AGENTS.md 中的相关描述以此为准。

## 核心原则

**里程碑切片完成后，自动执行 VPS 部署 + 验证 + GitHub 上传，无需逐项请示。**

例外：用户明确说"不要部署""不要提交""只本地检查"时跳过对应步骤。

---

## 完整 Closeout 流程（7 步）

```text
1. 本地门禁
2. 变更审查
3. VPS 部署
4. VPS 验证
5. 证据落盘
6. Git commit
7. GitHub 上传
```

> **Gitee 同步已退役**：`findings.md` OPS-022 已记录移除 `gitee` remote，不再作为强制步骤。如有特殊需要，可手动执行 `python scripts/push_dual_remotes.py`。

### Step 1: 本地门禁

```bash
# 生产代码改动 → 全量测试
python -m pytest --tb=short -q

# 纯文档/脚本 → focused 测试
python -m pytest tests/test_<related>.py -v

# 补充检查（按需）
ruff check .
```

**通过标准**: 0 failed，新测试覆盖新增代码 80%+。

### Step 2: 变更审查

```bash
git status --short
git diff --stat
```

- 只处理本轮相关文件
- 发现用户未说明的改动时保留并绕开，不做 reset/checkout
- 检查无 `.env`、token、密码混入

### Step 3: VPS 部署

```bash
# 标准部署（推荐）：读取 .env 中的 LIMA_DEPLOY_KEY_PATH / LIMA_DEPLOY_USE_TAR
python scripts/deploy_unified.py --slice core

# 同步 nginx 配置并部署 core（谨慎：会触碰 /etc/nginx）
python scripts/deploy_unified.py --slice core --sync-nginx

# 仅上传指定文件（不重启）
python scripts/deploy_unified.py --files <file1> <file2> --no-restart

# Dry-run（仅检查，不执行）
python scripts/deploy_unified.py --dry-run
```

**部署前必须**:
- 记录当前版本（`git log --oneline -1`）
- 记录备份位置（VPS `/opt/lima-router/backups/`）
- 确认 `.env` 中 `LIMA_DEPLOY_KEY_PATH` 指向有效私钥
- 确认 SSH 使用 `RejectPolicy`（非 `AutoAddPolicy`）

**部署流程**:
1. 自动检查 VPS 磁盘和内存容量
2. 在 VPS 上创建 tar 备份
3. 默认使用 tar/scp 批量上传（环境 `LIMA_DEPLOY_USE_TAR=1`），失败时回退到 SFTP
4. `systemctl restart lima-router`
5. 轮询 `/health`（liveness，最长 120s）与 `/health/ready`（readiness，最长 60s）等待服务完全就绪
6. readiness 成功后打印启动阶段耗时摘要

### Step 4: VPS 验证

```bash
# 健康检查（deploy_unified.py 自动执行）
curl -sf https://chat.donglicao.com/health

# 严格就绪探针（503 表示仍在启动或热身）
curl -sf https://chat.donglicao.com/health/ready

# 设备网关健康
curl -sf https://chat.donglicao.com/device/v1/health

# 切片 smoke（按需）
python scripts/smoke_<feature>_vps.py
```

**健康端点 503 场景**:

- `/health` 与 `/device/v1/health` 正常返回 200；在以下情况可能返回 503：
  - **启动错误**：`/health` 在 `startup.status=error`（关键启动阶段失败）时返回 503。
  - **严格未就绪**：`/health/ready` 在 `startup.status` 为 `starting`/`warming`/`error` 时返回 503，供负载均衡作为 readiness probe。
  - **生产未就绪**：`/device/v1/health` 在 `LIMA_RUNTIME_ENV=production` 且 `task_store` / `session_bus` 未跨进程共享时返回 503（`production_ready=false`）。
- 验证失败时应先检查响应体，区分「服务未就绪」与「启动错误」。

**聊天端点 rate limiter 默认值**:

- `/v1/chat/completions` 使用滑动窗口限流，默认 `WINDOW=60s`、`MAX_PER_WINDOW=120`。
- IDE 来源请求倍率为 `5`（即 600/分钟），普通请求倍率为 `1`。
- 超限时返回 **429**（非 503）。

**验证失败时**:
1. 收集日志: `ssh root@47.112.162.80 'journalctl -u lima-router -n 50 --no-pager'`
2. 检查进程: `ssh root@47.112.162.80 'systemctl status lima-router'`
3. 最小化修复 → 重新部署 → 重跑 smoke
4. 仍失败则 rollback: 从 `/opt/lima-router/backups/<label>/runtime-before.tgz` 恢复

### Step 5: 证据落盘

更新以下文件（按需）:

| 文件 | 内容 |
|------|------|
| `progress.md` | 本轮完成项、测试数量、部署结果 |
| `findings.md` | 调试发现、rollback 证据、残余风险 |
| `STATUS.md` | 项目状态变更（仅重大变更时） |

### Step 6: Git Commit

```bash
# 仅 stage 里程碑相关文件
git add <file1> <file2> ...

# Conventional commit
git commit -m "<type>: <description>"

# 类型: feat, fix, refactor, docs, test, chore, perf
```

**禁止**:
- `git add .` 或 `git add -A`（避免混入无关文件）
- 提交 `.env`、token、VPS 密码、本地数据库、生成缓存
- 提交 `.lima-data/`、`chroma_db/` 等数据目录

### Step 7: GitHub 上传

```bash
# 优先推送到 GitHub
git push origin HEAD

# 如果当前分支没有远程跟踪分支
git push -u origin HEAD
```

### Step 8（已退役）: Gitee 同步

Gitee 镜像同步已不再是强制 closeout 步骤。`findings.md` OPS-022 已记录移除 `gitee` remote。

如仍有手动同步需求：

```bash
# 需要先确认本地存在 gitee remote
git remote get-url gitee
python scripts/push_dual_remotes.py
```

---

## 常用部署脚本速查

| 切片 | 部署脚本 | 说明 |
|------|----------|------|
| 标准部署 | `scripts/deploy_unified.py --slice core` | 容量检查 + 备份 + tar/scp 上传 + 重启 + health/ready 等待 |
| 同步 nginx | `scripts/deploy_unified.py --slice core --sync-nginx` | 额外同步 `_nginx_chat_temp.conf` 并 reload nginx |
| 指定切片 | `scripts/deploy_unified.py --slice phase_a/phase_b/all` | 按切片部署 |
| 指定文件 | `scripts/deploy_unified.py --files a.py b.py` | 仅上传指定文件 |
| JDCloud 探测 | `scripts/check_jdcloud_node.py` | 只读烟雾，不部署 |
| 预提交门禁 | `scripts/run_pre_commit_check.py` | ruff + pytest 本地门禁 |
| 双远程推送 | `scripts/push_dual_remotes.py` | GitHub + Gitee 同步（Gitee 已退役） |

---

## 环境变量要求

```bash
# VPS 部署
LIMA_DEPLOY_KEY_PATH=~/.ssh/lima_deploy_ed25519  # SSH 私钥
LIMA_DEPLOY_KNOWN_HOSTS=~/.ssh/known_hosts       # SSH 主机密钥
LIMA_DEPLOY_USE_TAR=1                            # 使用 tar/scp 批量上传（推荐）
LIMA_DEPLOY_NOTIFY=1                             # 保留兼容开关；Telegram 通知已退役

# VPS 上运行时
LIMA_DRY_RUN=1                             # 默认关闭真实执行
LIMA_ALLOW_SHELL=0                         # 默认关闭 shell
LIMA_ALLOW_NETWORK=0                       # 默认关闭网络
LIMA_RUNTIME_ENV=development               # production 会启用生产就绪检查
LIMA_RATE_LIMIT_ENABLED=0                  # 默认关闭；开启后 /health 等端点可能返回 503
```

---

## 安全红线

1. **不提交凭据**: `.env`、API key、token、VPS 密码
2. **不放宽认证**: 不为通过 smoke 而关闭认证或扩大端口
3. **不 force-push**: 部署失败时 rollback，不强制推送
4. **不擅自打开开关**: 新能力默认关（env flag），需用户批准
5. **SSH 安全**: 使用 `RejectPolicy`，不用 `AutoAddPolicy`

---

## 自动化触发条件

Agent 在以下场景**自动执行**完整 closeout 流程：

- 里程碑切片完成（代码 + 测试通过）
- 运维修复完成（bug fix + 回归测试通过）
- 联调验证完成（多端测试通过）
- 质量审查修复完成（lint/type/test 修复）

Agent 在以下场景**跳过**部署/上传：

- 用户明确说"不要部署"
- 用户明确说"不要提交"
- 用户明确说"只本地检查"
- 仅修改文档（无代码变更）
- 测试未通过（禁止带失败部署）
