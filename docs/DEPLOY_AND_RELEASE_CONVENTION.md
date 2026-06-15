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
# 标准部署（推荐）
python scripts/deploy_unified.py

# 仅上传指定文件（不重启）
python scripts/deploy_unified.py --files <file1> <file2> --no-restart

# Dry-run（仅检查，不执行）
python scripts/deploy_unified.py --dry-run
```

**部署前必须**:
- 记录当前版本（`git log --oneline -1`）
- 记录备份位置（VPS `/opt/lima-router/backups/`）
- 确认 SSH 使用 `RejectPolicy`（非 `AutoAddPolicy`）

**部署流程**:
1. 自动检查 VPS 磁盘和内存容量
2. 在 VPS 上创建 tar 备份
3. SFTP 上传新文件
4. `systemctl restart lima-router`
5. 轮询 `/health` 等待服务就绪（最长 90s）

### Step 4: VPS 验证

```bash
# 健康检查（deploy_unified.py 自动执行）
curl -sf https://chat.donglicao.com/health

# 设备网关健康
curl -sf https://chat.donglicao.com/device/v1/health

# 切片 smoke（按需）
python scripts/smoke_<feature>_vps.py
```

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

### Step 8: Gitee 同步

```bash
# 推送到 Gitee 镜像
git push gitee HEAD

# 或使用双推脚本（如有）
python scripts/push_dual_remotes.py
```

---

## 常用部署脚本速查

| 切片 | 部署脚本 | 说明 |
|------|----------|------|
| 标准部署 | `scripts/deploy_unified.py` | 容量检查 + 备份 + SFTP + 重启 + health 等待 |
| JDCloud 探测 | `scripts/check_jdcloud_node.py` | 只读烟雾，不部署 |
| 预提交门禁 | `scripts/run_pre_commit_check.py` | ruff + pytest 本地门禁 |
| 双远程推送 | `scripts/push_dual_remotes.py` | GitHub + Gitee 同步 |

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
