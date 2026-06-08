# LiMa 自动部署与发布约定

> 权威文档。CLAUDE.md / AGENTS.md 中的相关描述以此为准。

## 核心原则

**里程碑切片完成后，自动执行 VPS 部署 + 验证 + GitHub/Gitee 上传，无需逐项请示。**

例外：用户明确说"不要部署""不要提交""只本地检查"时跳过对应步骤。

---

## 完整 Closeout 流程（8 步）

```text
1. 本地门禁
2. 变更审查
3. VPS 部署
4. VPS 验证
5. 证据落盘
6. Git commit
7. GitHub 上传
8. Gitee 同步
```

### Step 1: 本地门禁

```bash
# 生产代码改动 → 全量测试
python -m pytest tests/ -q --ignore=tests/test_ci_gates.py

# 纯文档/脚本 → focused 测试
python -m pytest tests/test_<related>.py -v

# 补充检查（按需）
ruff check . --config ruff.toml
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
# 方式 A: 全量部署（核心模块变更时）
python deploy_v3.py

# 方式 B: 切片部署（单模块变更时）
python scripts/deploy_<slice>_vps.py

# 方式 C: VPS bundle（大量文件变更时）
python scripts/deploy_vps_bundle.py
```

**部署前必须**:
- 记录当前版本（`git log --oneline -1`）
- 记录备份位置（VPS 上 `.bak.*` 文件）
- 确认 SSH 使用 `RejectPolicy`（非 `AutoAddPolicy`）

**部署流程**:
1. 备份 VPS 上的旧文件
2. SFTP 上传新文件
3. 重启服务（`pkill -f server.py && nohup python server.py &`）
4. 等待端口 8080 就绪

### Step 4: VPS 验证

```bash
# 健康检查
curl -s http://47.112.162.80:8080/health

# 切片 smoke（按需）
python scripts/smoke_<feature>_vps.py

# 模型路由验证
curl -s http://47.112.162.80:8080/v1/models | python -m json.tool
```

**验证失败时**:
1. 收集日志: `ssh root@47.112.162.80 'tail -50 /opt/lima-router/nohup.out'`
2. 检查进程: `ssh root@47.112.162.80 'ps aux | grep server.py'`
3. 最小化修复 → 重新部署 → 重跑 smoke
4. 仍失败则 rollback: `ssh root@47.112.162.80 'cp /opt/lima-router/<file>.bak.* /opt/lima-router/<file>'`

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

### Step 8: Gitee 同步

```bash
# 推送到 Gitee 镜像
git push gitee HEAD

# 或使用双推脚本（如有）
python scripts/push_dual_remotes.py
```

---

## 常用部署脚本速查

| 切片 | 部署脚本 | Smoke 脚本 |
|------|----------|------------|
| 核心路由 | `deploy_v3.py` | `curl /health` |
| 全量 bundle | `deploy_vps_bundle.py` | `curl /health` + `/v1/models` |
| Agent 任务 | `deploy_prod008_slice.py` | `smoke_prod008_learning_loop_e2e.py` |
| Webhook | `deploy_github_webhook.py` | `smoke_github_webhook_public.py` |
| Channel GW | `deploy_channel_gateway.py` | `curl /health` |
| 可靠性 | `deploy_reliability_ops.py` | Healthchecks + `/health` smoke |

---

## 环境变量要求

```bash
# VPS 部署
LIMA_DEPLOY_KEY_PATH=~/.ssh/id_ed25519    # SSH 私钥
LIMA_DEPLOY_KNOWN_HOSTS=~/.ssh/known_hosts # SSH 主机密钥
LIMA_DEPLOY_NOTIFY=1                       # 保留兼容开关；Telegram 通知已退役

# VPS 上运行时
LIMA_DRY_RUN=1                             # 默认关闭真实执行
LIMA_ALLOW_SHELL=0                         # 默认关闭 shell
LIMA_ALLOW_NETWORK=0                       # 默认关闭网络
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
